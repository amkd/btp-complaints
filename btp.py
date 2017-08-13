#!/usr/local/bin/python2
from PIL import Image
from geopy.geocoders import GoogleV3
from geopy.exc import GeocoderServiceError
import gi; gi.require_version('GExiv2', '0.10')
from gi.repository.GExiv2 import Metadata, Orientation
from cmd import Cmd
import mechanize
import functools, glob, os, re, subprocess, time
from BeautifulSoup import BeautifulSoup

gloc = GoogleV3( api_key=os.environ['GAPI_KEY'] )
btpName = os.environ['BTP_USER']
btpMobile = os.environ['BTP_MOBILE']
btpEmail = os.environ['BTP_EMAIL']

newsize = ( 704,  528 )

class Process( Cmd ):
    def __init__( self, infile ):
        Cmd.__init__( self )
        self.infile = infile
        self.regNo = None
        self.violation = ''
        self.metadata = None
        self.vioTypes = [ 'NO PARKING|N',
                          'DEFECTIVE NUMBER PLATE|Y',
                          'NOT WEARING SEAT BELT|N',
                          'ONEWAY/NOENTRY|N',
                          'RIDING ON FOOTPATH|N',
                          'RIDING WITHOUT A HELMET|Y',
                          'NOT WEARING HELMET - PILLION RIDER|Y',
                          'STOPPED ON ZEBRA CROSS/NEAR TRF LIGHT|N',
                          'TAKING A U-TURN WHERE U-TURN IS PROHIBITED|N',
                          'TRIPLE RIDING|N',
                          'USING MOBILEPHONE|N',
                          'VIOLATING LANE DISCIPLINE|N',
                          'USING BLACK FILM/OTHER MATERIALS|Y',
                          'JUMPING TRAFFIC SIGNAL|N',
                          'WRONG PARKING|N',
                          'PARKING ON FOOTPATH|N' ]

        im = Image.open( self.infile )
        m = Metadata()
        m.open_path( self.infile )
        m.clear_tag( 'Exif.Image.Make' )
        m.clear_tag( 'Exif.Image.Model' )
        m.clear_tag( 'Exif.Image.Software' )
        m.clear_tag( 'Exif.Photo.LensMake' )
        m.clear_tag( 'Exif.Photo.LensModel' )
        m.erase_exif_thumbnail()


        newPath = 'pending/' + os.path.basename( infile )
        im.thumbnail( newsize )
        im.save( newPath )

        self.metadata = m
        self.im = im
        _ = subprocess.call([ "open", self.infile ] )

    def complete_registration( self, text, line, begidx, endidx ):
        return [ 'KA' ]

    def do_registration( self, arg ):
        if not arg:
            discard = raw_input( 'Delete the image? [Y]|N ' )
            if not discard:
                print 'Deleting %s ...' % self.infile
                os.unlink( self.infile )
            return True
        self.regNo = arg
        return self.finish()

    def complete_viotype( self, text, line, begidx, endidx ):
        return [ '%s' % x for x in self.vioTypes if x.startswith( text ) ]

    def do_viotype( self, arg ):
        if not arg:
            return False
        self.violation = arg
        return self.finish()

    def do_quit( self, arg):
        return True

    do_EOF = do_quit

    def finish( self ):
        if self.regNo and self.violation:
            print self.regNo, self.violation
            newPath = 'pending/' + os.path.basename( self.infile )
            self.metadata.set_comment( self.regNo + '@' + self.violation )
            if self.metadata.get_orientation() == Orientation.ROT_90:
                self.im.rotate(-90).save( newPath )
                self.metadata.set_orientation( Orientation.NORMAL )

            try:
                self.metadata.save_file( newPath )
            except Exception as e:
                print e
            return True
        return False

    def emptyline( self ):
        pass

class BlrPublicEye( Cmd ):
    def __init__( self, imageDir ):
        Cmd.__init__( self )
        self.prompt = 'PublicEye #'
        self.imageDir = imageDir
        self.images = []
        self.procImages = []
        self.compIds = {}
        for infile in glob.glob( imageDir + "/*.JPG" ) + \
		      glob.glob( imageDir + "/*.jpg" ):
            self.images.append( os.path.basename( infile ) )
            m = Metadata()
            m.open_path( infile )
            comment = m.get_comment()
            if comment and len( comment.split('@') ) == 2:
                self.procImages.append( os.path.basename( infile ) )

        for infile in sorted( glob.glob( 'submitted/' + "/*.JPG" ) + \
		      glob.glob( 'submitted' + "/*.jpg" ),
		      key=lambda x: int( os.stat( x ).st_ctime ),
		      reverse=True ):
            self.images.append( os.path.basename( infile ) )
            m = Metadata()
            m.open_path( infile )
            comment = m.get_comment()
            if comment and len( comment.split('@') ) == 3:
                compDetails = comment.split('@')
                pat = re.compile( r'.+No. is : ([0-9]+).*')
                result = pat.match( compDetails[2] )
                if result:
                    self.compIds[result.groups()[0]] = ( compDetails[0],
                            compDetails[1] )
        print 'Total of %d complaints submitted so far' % len( self.compIds )

    def emptyline( self ):
        pass

    def imageNames( self, text ):
        return [ '%s' % x for x in self.images if x.startswith( text ) ]

    def procImageNames( self, text ):
        return [ '%s' % x for x in self.procImages if x.startswith( text ) ]

    def do_allcomplaints( self, arg ):
        for comp in sorted( self.compIds, key=lambda x: int(x), reverse=True ):
            complaintStatus( comp )

    def do_quit( self, arg ):
        print 'Exiting ...'
        import sys
        sys.exit( 0 )

    do_EOF = do_quit

    def subCompIds( self, text ):
        return [ '%s' % x for x in self.compIds if x.startswith( text ) ]

    def complete_checkstatus( self, text, line, begidx, endidx ):
        return self.subCompIds( text )

    def do_checkstatus( self, arg ):
        if arg == '':
            print 'Error: Please enter complaint id'
            return
        complaintStatus( arg )

    def do_finedetails( self, arg ):
        if arg == '':
            print 'Error: Please enter vehicle registration number'
            return
        fineStatus( arg )

    def complete_submit( self, text, line, begidx, endidx ):
        return self.procImageNames( text )

    def do_submit( self, arg ):
        if arg == '':
            print 'Error: Please enter image to submit'
            imageName = self.actImage
        elif arg in self.procImages and \
             os.path.exists( '%s/%s' % ( self.imageDir, arg ) ) :
            imageName = arg
        else:
            print 'Error: image %s does not exist' % arg
            return
        img_path = '%s/%s' % ( self.imageDir, imageName )
        submitComplaint( img_path )
        self.procImages.remove( imageName )

    def complete_show( self, text, line, begidx, endidx ):
        return self.imageNames( text )

    def do_show( self, arg ):
        if arg == '':
            print 'Error: Please enter image to show'
            return False
        elif arg in self.images:
            imageName = arg
        else:
            print 'Error: image %s does not exist' % arg
            return

        m = Metadata()
        img_path = '%s/%s' % ( self.imageDir, imageName )
        if not os.path.exists( img_path ):
            img_path = '%s/%s' % ( 'submitted', imageName )

        m.open_path( img_path )

        t = m.get_tag_string('Exif.Photo.DateTimeOriginal')
        ts = time.strptime(t, '%Y:%m:%d %H:%M:%S')

        retryCount = 3
        location = 'Unknown Address'
        while retryCount:
            try:
                loc = gloc.reverse( '%f, %f' % ( m.get_gps_latitude(),
                                    m.get_gps_longitude() ) )
                location = ','.join( loc[1].address.split(',')[:4] )
                break
            except geopy.exc.GeocoderServiceError as e:
                print e
                time.sleep(0.5)
                retryCount -= 1

        comment = m.get_comment()
        regno = ''
        vtype = ''
        complaint = ''
        if comment:
            reg_v = comment.split('@')
            regno = reg_v[0]
            vtype = reg_v[1]
            if len( reg_v ) > 2:
                complaint = reg_v[2]

        print 'Image: %s' % imageName
        print 'Violation Date & Time: %s' % time.strftime( '%m/%d/%Y %H:%S', ts )
        print 'Location: %s' % location
        if regno:
            print 'Vehicle Registration Number: %s' % regno
        if vtype:
            print 'Violation Type: %s' % vtype
        if complaint:
            print complaint

    def complete_processimages( self, text, line, begidx, endidx ):
        return [ 'raw' ]

    def do_processimages( self, arg ):
        imageDir = 'raw' if arg == '' else arg
        fileList = []
        for infile in glob.glob( imageDir + "/*.JPG") + glob.glob( imageDir + "/*.jpg"):
            fname, ext = os.path.splitext( infile )
            newPath = 'pending/' + os.path.basename( infile )
            if os.path.exists( newPath ):
                continue
            fileList.append( infile )
        if not fileList:
            print 'No images to be processed'
            return False

        for infile in fileList:
            print 'Processing image file: %s' % os.path.basename( infile )
            cl = Process( infile )
            cl.prompt = self.prompt[:-1] + ':%s >' % infile
            cl.cmdloop()


    def complete_dump( self, text, line, begidx, endidx ):
        return self.imageNames( text )

    def do_dump( self, arg ):
        if arg == '':
            if not self.actImage:
                print 'Error: No image is currently selected'
                return
            imageName = self.actImage
        elif arg in self.images:
            imageName = arg
        else:
            print 'Error: image %s does not exist' % arg
            return

        m = Metadata()
        img_path = '%s/%s' % ( self.imageDir, imageName )
        m.open_path( img_path )

        t = m.get_tag_string('Exif.Photo.DateTimeOriginal')
        ts = time.strptime(t, '%Y:%m:%d %H:%M:%S')

        rc = subprocess.call([ "open", "-W", img_path ] )
        location = gloc.reverse( '%f, %f' % ( m.get_gps_latitude(),
                                 m.get_gps_longitude() ) )

    def do_exit( self, arg):
        return True

def submitComplaint( infile ):
    m = Metadata()
    m.open_path( infile )

    comment = m.get_comment()
    try:
        reg_v = comment.split('@')
    except AttributeError as e:
        print e
        return

    if len( reg_v ) > 2:
        print 'Complaint has already been submitted ...', reg_v[2]
        return

    t = m.get_tag_string('Exif.Photo.DateTimeOriginal')
    ts = time.strptime(t, '%Y:%m:%d %H:%M:%S')

    im = Image.open( infile )
    im.show()
    br = mechanize.Browser()
    br.set_handle_robots( True )
    br.open('http://www.bangaloretrafficpolice.gov.in/PublicEye/PublicEyePost.aspx')
    br.select_form(name="form1")

    location = gloc.reverse( '%f, %f' % ( m.get_gps_latitude(), m.get_gps_longitude() ) )

    print 'Image: %s' % infile
    print 'Violation Date & Time: %s' % time.strftime( '%m/%d/%Y %H:%S', ts )
    print 'Location: %s' % ','.join( location[1].address.split(',')[:4] )
    print 'Vehicle Registration Number: %s' % reg_v[0]
    print 'Violation Type: %s' % reg_v[1]
    x = raw_input( 'Hit Enter to continue ' )

    br.set_all_readonly( False )
    br['txtDate'] = time.strftime( '%m/%d/%Y', ts )
    br['ddlHours'] = [ "%02d" % ts.tm_hour ]
    br['ddlMinutes'] = [ "%02d" % ts.tm_min ]
    br['txtVioPlace'] = ','.join( location[1].address.split(',')[:4] )
    br['txtPersonName'] = btpName
    br['txtMobileno'] = btpMobile
    br['txtEmailid'] = btpEmail
    br['txtVehicleRegno'] = reg_v[0]
    br['ddlCategory'] = [ "%s" % reg_v[1] ]
    br['txtRemark'] = raw_input( 'Enter remark => ' )

    br.add_file( open( infile, 'rb' ), 'image/jpg', os.path.basename( infile ) )

    #for c in br.form.controls:
    #    if c.type == 'hidden':
    #        continue
    #    print c.name, c.type, br[c.name]
    print 'Submitting complaint'
    print 'File: %s' % infile
    print br['txtVioPlace'], br['txtVehicleRegno'], br['txtDate']
    print br['ddlCategory'], br['txtRemark']

    resp = br.submit()
    x = raw_input( 'Hit Enter to continue ' )

    complaint_id = BeautifulSoup( resp.read() ).findAll('span')[-1]
    print complaint_id.text
    m.set_comment( '%s@%s' % ( comment, complaint_id.text ) )
    try:
        m.save_file( infile )
        os.rename( infile, 'submitted/%s' % os.path.basename( infile ) )
        os.unlink( 'raw/%s' % os.path.basename( infile ) )
    except Exception as e:
        print e

def complaintStatus( complaintId ):
    br = mechanize.Browser()
    br.set_handle_robots( True )
    br.open('http://www.bangaloretrafficpolice.gov.in/PublicEye/ComplaintStatus.aspx')
    br.select_form(name="form1")
    br.set_all_readonly( False )

    br['txtCompno'] = '%s' % complaintId
    resp = br.submit()
    x = BeautifulSoup(resp.read())
    tables = x.findAll('table', { 'id' : 'tbl_Details' })
    if not tables:
        print 'No fines have been registered against this vehicle'
        return

    fineTbl = tables[0]
    vregNo      = fineTbl.findAll( 'div', { 'id' : 'divRegno' } )[0].text
    vType       = fineTbl.findAll( 'div', { 'id': 'divVtype' } )[0].text
    vRemarks    = fineTbl.findAll( 'div', { 'id': 'divPremarks' } )[0].text
    vrDate      = fineTbl.findAll( 'div', { 'id': 'divRdate' } )[0].text
    vioDate     = fineTbl.findAll( 'div', { 'id': 'divVdateTm' } )[0].text
    compStatus  = fineTbl.findAll( 'div', { 'id': 'divBS2' } )[0].text

    if 'is booked' in compStatus:
        status = 'Booked'
    elif 'is rejected' in compStatus:
        status = 'Rejected'
    elif 'is under process' in compStatus:
        status = 'Under process'
    else:
        status = 'Unknown'

    print status, complaintId, vregNo, vType, vioDate, vrDate, vRemarks[:35]

def fineStatus( vregNo ):
    br = mechanize.Browser()
    br.set_handle_robots( True )
    br.open('http://www.bangaloretrafficpolice.gov.in/bpsfinedetails/bpsfinedetails.aspx')
    br.select_form(name="form1")

    import re
    pat = re.compile( r'([A-Z]{2})([0-9]{2})[ ]*([A-Z]+)([0-9]+)' )
    vmat = pat.match( vregNo )
    if not vmat:
        return
    result = vmat.groups()

    br['txtRegNumber1'] = result[0]
    br['txtRegNumber2'] = result[1]
    br['txtRegNumber3'] = result[2]
    br['txtRegNumber4'] = result[3]
    resp = br.submit()

    x = BeautifulSoup(resp.read())
    tables = x.findAll('table', { 'id' : 'dgFineDetails' })
    if not tables:
        print 'No fines have been registered against this vehicle'
        return

    fineTbl = tables[0]
    for row in fineTbl.findAll('tr'):
        col = row.findAll('td')
        if not col:
            continue
        regNo       = col[0].text
        noticeNo    = col[1].text
        vioDate     = col[2].text
        vioTime     = col[3].text
        vioType     = col[4].text
        fineAmt     = col[5].text
        print regNo, vioTime, vioDate, vioType

interp = BlrPublicEye( 'pending' )

if __name__ == '__main__':
    while True:
        try:
            interp.cmdloop()
        except KeyboardInterrupt:
            print '\nInterrupted ...'
        except EOFError:
            print 'Exiting ...'
            break
