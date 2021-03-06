import cv,time,math,serial
'''As of 3/24/13 this program tracks two specified colors and draws rectangles around them in a displayed
image. When the two colors line up within a certain bounds, green circles are plaed about their centroids
to indicate that a second criteria has been met i.e. they are the right color and they are vertically 
aligned. The serial is not working properly, neither is the distance calculator. When the distances are 
known, the location of the stereo rig can be found with respect to the beacon coordinate frame using the
circleIntersections() function.

To Do:  [Create third criteria of specific color above or below another color]
	Get Serial working
	Get distance working, specifically distance to beacon 1, beacon 2, etc.
	Make circleIntersections() reject points far away

3/25/13: Accomplished the task of adding a third criteria of having a specific color above or below another.
3/27/13: Color detection is now performed on the undistorted images. Undistortion is accomplished using the
chessBoardCalibration.py program.
	 The color detection program is now based on specified lists of upper and lower Hue bounds.
	 Serial communication seems to be working, but it has not been tested with an Arduino yet.
'''
########################################################################################################
def findBeacons(frame,flag,upper,lower):
	'''This function is used to find the location of specified colors within an image. The function
	calculates and draws a bounding rectangle around the specified colors and returns this image 
	as well as the centroid of the rectangle. Then this function calls some test functions to 
	determine if the found blob is a beacon.'''

	#flags needed to determine if this function is being called by the left or right camera
	if flag == 'L':
		holderImage = cv.QueryFrame(captureL)#hold the real image
		colorImage = undistort(holderImage,flag)#undistort the image
	elif flag == 'R':
		holderImage = cv.QueryFrame(captureR)#hold the real image
		colorImage = undistort(holderImage,flag)#undistort the image

	imdraw=cv.CreateImage(cv.GetSize(frame),8,3)#create blank image to draw on
	cv.SetZero(imdraw)#clear the array
	cv.Flip(colorImage,colorImage,1)#flip the captured image for more natural viewing
	cv.Smooth(colorImage, colorImage, cv.CV_GAUSSIAN, 3, 0)#smooth image to reduce noise

	threshImage=specifyColor(colorImage,upper,lower)#returns the specified color range thresholded image
	
	#image processing magic
	cv.Erode(threshImage,threshImage,None,3)
	cv.Dilate(threshImage,threshImage,None,10)

	img2=cv.CloneImage(threshImage)#reassign images
	storage = cv.CreateMemStorage(0)#memory storage location needed for next function
	
	#this cvFunction finds contours that match the specified colors
	contour = cv.FindContours(threshImage, storage, cv.CV_RETR_CCOMP, cv.CV_CHAIN_APPROX_SIMPLE)
	
	#define new lists
	points = []
	centroidx = []
	centroidy = []

	#cycle through all of the contours and draw red bounding rectangles around them. This is helpful
	#in showing what the camera is detecting with the first detection criteria.
	while contour:
		# Draw bounding rectangles
		bound_rect = cv.BoundingRect(list(contour))#draw a rectangle around the contours
		contour = contour.h_next()#h_next() points to the next reference in the list
	
		#Store vertices of the rectangle in order to draw it on the image.
		pt1 = (bound_rect[0], bound_rect[1])#assign vertex 1 
		pt2 = (bound_rect[0] + bound_rect[2], bound_rect[1] + bound_rect[3])#assign vertex 2
		
		#add the values of points 1 and 2 to the list points[]		
		points.append(pt1)
		points.append(pt2)

		#draw a rectangle onto colorImage. pt1 and pt2 are the rectangles vertices, then the color
		cv.Rectangle(colorImage, pt1, pt2, cv.CV_RGB(255,0,0), 1)
	
		#Calculate the centroids, which will be used in following tests
		centroidx.append(cv.Round((pt1[0]+pt2[0])/2))#round the average of the x-coordinates of the two points
		centroidy.append(cv.Round((pt1[1]+pt2[1])/2))#round the average of the y-coordinates of the two points
	
	#Begin testing to find beacons!
	colorImage,beaconx,beacony = testBeacons(centroidx,centroidy,colorImage)

	return colorImage,beaconx,beacony
	
########################################################################################################
def undistort(holderImage,flag):
	'''Use the calibration matrices calculated using chessboardCalibration.py to undistort the left and right
	cameras before finding beacons.'''

	if flag == 'L':
		colorImage=cv.CreateImage(cv.GetSize(holderImage),8,3)#remap the camera frame
		mapxL = cv.CreateImage( cv.GetSize(imageL), cv.IPL_DEPTH_32F, 1 );
		mapyL = cv.CreateImage( cv.GetSize(imageL), cv.IPL_DEPTH_32F, 1 );
		cv.InitUndistortMap(intrinsicL,distortionL,mapxL,mapyL)
		cv.Remap( holderImage, colorImage, mapxL, mapyL )
	elif flag == 'R':
		colorImage=cv.CreateImage(cv.GetSize(holderImage),8,3)#create blank image called imdraw
		mapxR = cv.CreateImage( cv.GetSize(imageR), cv.IPL_DEPTH_32F, 1 );
		mapyR = cv.CreateImage( cv.GetSize(imageR), cv.IPL_DEPTH_32F, 1 );
		cv.InitUndistortMap(intrinsicR,distortionR,mapxR,mapyR)
		cv.Remap( holderImage, colorImage, mapxR, mapyR)
	return colorImage
########################################################################################################
def specifyColor(im,upper,lower):
	'''Convert RGB into HSV for easy colour detection and threshold it with specific colors as white 		
	and all other colors as black,then return that image for processing'''
	#Create a blank image to store the converted RGB2HSV image
	imghsv=cv.CreateImage(cv.GetSize(im),8,3)
	cv.CvtColor(im,imghsv,cv.CV_BGR2HSV)

	#create the blank images to store the 2 specified color images
	imgColor1=cv.CreateImage(cv.GetSize(im),8,1)
	imgColor2=cv.CreateImage(cv.GetSize(im),8,1)
	
	#create blank image to hold complete threshold image
	imgthreshold=cv.CreateImage(cv.GetSize(im),8,1)
	
	# Select a range of colors (source, lower bound, upper bound, destination)
	cv.InRangeS(imghsv,cv.Scalar(lower[0],90,75),cv.Scalar(upper[0],255,255),imgColor1)
	cv.InRangeS(imghsv,cv.Scalar(lower[1],90,75),cv.Scalar(upper[1],255,255),imgColor2)

	#adds the color arrays to imgthreshold
	cv.Add(imgColor1,imgColor2,imgthreshold)
	return imgthreshold 
########################################################################################################
def testBeacons(centroidx,centroidy,colorImage):
	'''This function is used to run all of the tests on the image to determine the location of the beacon. 
	Tests include:
		-alignmentTest: determine if centroids vertically aligned
		-colorTest: determine if correct color is above the other
		-cicleTest: is the blob a circle?**To be implemented
	'''		

	#test all detected blobs if their centroids are vertically aligned
	colorImage,beaconx,beacony = alignmentTest(centroidx,centroidy,colorImage)
	#test all of the blobs that pass the first test if a specified color is on top of another	
	colorImage,beaconx,beacony = colorTest(beaconx,beacony,colorImage,upper,lower)
	return colorImage,beaconx,beacony
########################################################################################################
def alignmentTest(centroidx,centroidy,colorImage):
	'''Determine if the detected bounding rectangles are within a specified distance of one another in order to
	check if we are looking at the beacon by cycling through all of the rectangles.'''

	#lists to store successful blob locations
	beaconx = []	
	beacony = []

	#cycle through all blobs with respect to eachother
	for i in range(len(centroidx)):
		for j in range(len(centroidx)):
			#skip if we're looking at the same blob
			if i == j:
				continue
			else:
				#if the centroids of the two detected objects line up within a allowable error
				a =  (centroidx[j] + 0.05*centroidx[j])
				b =  (centroidx[j] - 0.05*centroidx[j])
				if (b <= centroidx[i] <= a):
					#if we find a beacon, save the centroid location
					beaconx.append(centroidx[i])
					beacony.append(centroidy[i])
		
					#draw a green circle on the image to indicate beacon centroid location
					cv.Circle(colorImage,(centroidx[i],centroidy[i]),20,cv.CV_RGB(0,255,0))

	#return all of the parameters that we want
	return colorImage,beaconx,beacony
########################################################################################################
def colorTest(centroidx,centroidy,colorImage,upper,lower):
	'''Detect the color of the centroids of objects that met the previous criteria. If the colors are within
	the allowable range and in the correct order, then we return that as a definite beacon.'''

	#new list of final beacon locations (final since there are only two tests right now)
	beaconFinalx = []
	beaconFinaly = []
	
	#convert image to HSV for processing
	colorTestImage = cv.CreateImage(cv.GetSize(colorImage),8,3)
	cv.CvtColor(colorImage,colorTestImage,cv.CV_BGR2HSV) 

	k = 0 #beacon counter
	for i in range(len(centroidx)):
		for j in range(len(centroidx)):
			if i == j:
				continue
			else:
				a =  (centroidx[j] + 0.05*centroidx[j])
				b =  (centroidx[j] - 0.05*centroidx[j])
				
				#return the HSV value of pixel in a 1x3 list
				color1 = cv.Get2D(colorTestImage,centroidy[j],centroidx[j])#coordinates given in (y,x) 
				color2 = cv.Get2D(colorTestImage,centroidy[i],centroidx[i])
				#(if color2 = red and color1 = blue)
				if ((lower[0] <= color2[0] <= upper[0]) and (lower[1]<= color1[0] <= upper[1])):
					#This ensures that the blobs we're looking at are aligned. There should be a way
					#to use alignmentTest to not have to do this again.
					if ((centroidy[j] > centroidy[i]) and (b <= centroidx[i] <= a)):
						beaconFinalx.append((centroidx[j]+centroidx[i])/2)
						beaconFinaly.append((centroidy[j]+centroidy[i])/2)
						cv.Circle(colorImage,(beaconFinalx[k],beaconFinaly[k]),30,cv.CV_RGB(255,255,0),10)	
						k = k+1
	
	#return all of the parameters that we want
	return colorImage,beaconFinalx,beaconFinaly
########################################################################################################
def calculateDistance(p1,p2):
	'''This function calculates the distance from the stereo rig to the beacons. The function
	recieves the pixel location of the centroid of the beacon and uses the pixel disparity to 
	calculate the distance to the beacon.'''

	offset = abs(p1-p2)
	eyeSep = 12.4 #cm
	factor = 555.0
	distance = math.tan(1.5707 - math.atan(offset/factor))*eyeSep
	return distance
########################################################################################################
def circleIntersections(x1,y1,r1,x2,y2,r2):
    """Calculate the intersection points of two circles with known radii and known x and y coordinates"""
    
    dx = x2-x1 #calculate the horizontal distance between the two beacons
    dy = y2-y1 #calculate the vertical distance between the two beacons
    d = math.sqrt(dx*dx + dy*dy) #calculate the absolute distance between the beacons

    #check for solution feasibility
    if (d > r1 + r2):
        print('The circles are seperate')
        return 0
    elif (d < math.fabs(r1 - r2)):
        print('One circle is contained within the other')
        return 0
    elif (d == 0 and r1 == r2):
        print('The circles are coincident')
        return 0

    #Now calculate the intersection points for feasible problems
    a = (r1*r1 - r2*r2 + d*d)/(2*d)
    h = math.sqrt(r1*r1 - a*a)
    x3 = x1 + a*dx/d
    y3 = y1 + a*dy/d

    xIntersect1 = x3 + h*dy/d
    yIntersect1 = y3 - h*dx/d
    xIntersect2 = x3 - h*dy/d
    yIntersect2 = y3 + h*dx/d

    #display the result (This would normally just be used in the 
    str1 = 'The first intersection points are (',xIntersect1,',',yIntersect1, ')'
    print(str1)
    str2 = 'The second intersection points are (', xIntersect2,',', yIntersect2, ')'
    print(str2)
    return 0#replace this with intersection points
	
########################################################################################################
def arduinoCom(leftMotor,rightMotor):
	'''This establishes serial communication with the arduino via pySerial, allowing this program
	to send signals to the actuators. Currently this isn't really doing anything, also I don't have
	the PID program written.'''
	ser.write('l')
	ser.write(chr(leftMotor))
	ser.write('r')
	ser.write(chr(rightMotor))
	return 0

########################################################################################################
#initalize parameters
#initiate the camera captures and capture a frame
captureL=cv.CaptureFromCAM(1)
cv.SetCaptureProperty(captureL,cv.CV_CAP_PROP_FRAME_WIDTH,640)#set the resolution of the cameras 
cv.SetCaptureProperty(captureL,cv.CV_CAP_PROP_FRAME_HEIGHT,480)
captureR=cv.CaptureFromCAM(2)
cv.SetCaptureProperty(captureR,cv.CV_CAP_PROP_FRAME_WIDTH,640)#set the resolution of the cameras 
cv.SetCaptureProperty(captureR,cv.CV_CAP_PROP_FRAME_HEIGHT,480)
imageL=cv.QueryFrame(captureL)
imageR=cv.QueryFrame(captureR)
# Load all of the parameters from the chessboard calibration programsize
intrinsicL = cv.Load("IntrinsicsL.xml")
distortionL = cv.Load("DistortionL.xml")
intrinsicR = cv.Load("IntrinsicsR.xml")
distortionR = cv.Load("DistortionR.xml")
print " loaded all distortion parameters"

#define the upper and lower Hue values of desired beacon colors in lists
upper = [10,104]
lower = [0,95]

ser = serial.Serial('/dev/tty2', 9600)#open the serial port
time.sleep(0.5)#give some time to establish the connection

#Begin 
while(1):
	#capture the images from the camera to process
	imageL=cv.QueryFrame(captureL)
	tL = cv.CloneImage(imageL);
	imageR=cv.QueryFrame(captureR)
	tR = cv.CloneImage(imageR);	

	try:
		#attempt to detect and calculate distance to beacons
		im_drawL=cv.CreateImage(cv.GetSize(imageL),8,3)
		im_drawL,beaconLx,beaconLy = findBeacons(imageL,'L',upper,lower)#find beacon Camera 1
		im_drawR=cv.CreateImage(cv.GetSize(imageR),8,3)
		im_drawR,beaconRx,beaconRy = findBeacons(imageR,'R',upper,lower)#find beacon Camera 2
		if (len(beaconLx) == 0 or len(beaconRx) == 0):
			a	#force an error because my code doesn't want to 
		for i in range(len(beaconLx)):
			distance = calculateDistance(beaconLx[i],beaconRx[i])#calculate distance
			print distance

	#Handle error if no beacon detected
	except:	
		print "There is no beacon detected"

	#display the undistorted images with bounding rectangles
	cv.ShowImage( "CalibrationL", im_drawL )
	cv.ShowImage( "CalibrationR", im_drawR )
	arduinoCom(5,6)
	c = cv.WaitKey(33)
	if c==1048603:# enter esc key to exit
		break
		
ser.close()#close the serial port
print "everything is fine, yay"#signal end of program
