import cv2
import numpy as np



def detect_fish(img, bg, image_scale, dilate_size, color_invert, body_threshold, real_fish_px_range):
    """
    Free swimming fish tracking in two steps
    First, we identify the fish by comparing the background and current frames
    Next, we zoom into the detected fish and detect the head, as well as calculating the body orientation
    """
    # Compare frame and background. Usually fish is darker than the background (color_invert=True)
    # Anyways in the following only fish pixels should be positive (and 0 otherwise)
    if not color_invert:
        diff_img = cv2.subtract(img, bg) # this does not do overflow
    else:
        diff_img = cv2.subtract(bg, img)

    # downsampling, if necessary
    if image_scale != 1:
        rescaled_img = cv2.resize(diff_img, None, fx=image_scale, fy=image_scale, interpolation=cv2.INTER_AREA)
    else:
        rescaled_img = diff_img

    # thresholding for body detection
    body_img = cv2.threshold(rescaled_img, body_threshold, 128, cv2.THRESH_BINARY)[1]
    # erosion followed by dilation to denoise and fatten
    body_img = cv2.erode(body_img, cv2.getStructuringElement(cv2.MORPH_RECT, (1,)*2), iterations = 1)
    body_img = cv2.dilate(body_img, cv2.getStructuringElement(cv2.MORPH_RECT, (dilate_size,)*2), iterations = 1)

    # For the sake of visualization, we label the fish body, fish head, and the bounding box for the fish
    # with different shades of grey
    visualization_image = body_img

    # Detect fish as a connected region with the largest among ones with appropriate size
    n_labels, _, stats, centroids = cv2.connectedComponentsWithStats(body_img)

    is_appropriate_size = (stats[:,-1] > real_fish_px_range[0]) * (stats[:,-1] < real_fish_px_range[1])

    # nothing found
    if not any(is_appropriate_size):
        # There will always be at least one label (i.e., background)
        # If we cannot find the fish body, we will just return nan
        return np.nan, np.nan, np.nan, visualization_image, (0,)*4
    
    # This needs to be updated if we want to do multi fish tracking
    fish_id = np.argmax(stats[:, -1]*is_appropriate_size)
    cent_x, cent_y = centroids[fish_id] / image_scale # we will always operate in the px coordinate of the original frame

    # slice fish
    xpx, ypx, wpx, hpx, _ = (stats[fish_id] / image_scale).astype(int)
    fish_snippet = diff_img[ypx:(ypx+hpx), xpx:(xpx+wpx)]

    # update the viusalization image
    slice_y = slice(int(ypx*image_scale), int((ypx+hpx)*image_scale))
    slice_x = slice(int(xpx*image_scale), int((xpx+wpx)*image_scale))
    visualization_image[slice_y, slice_x] += 127

    # First, find the orientation of the fish body by doing PCA
    # mu11 are covariance of (x, y) positive pixel positions and
    # mu20, mu02 are respectively variances in x, y dimensions
    # Think of the covariance matrix M = [[mu20, mu11], [mu11, mu02]]
    # The angle of the first eigen vector of M is going to be the long axis of the object
    # Let  the eigenvector v = (cos(theta), sin(theta))) and eigenvalues lambda
    # Now by expanding the character equation Mv=lambda*v, we get
    # tan(theta) = (lambda-mu20)/mu11 [E1] (note if mu11=0, M is diagonal and theta is 0 or pi/2)
    # At the same time, we can erase theta dependent terms and solve a quadratic equation
    # for lambda to get lambda = [(mu20+mu02)+sqrt((mu20-mu02)**2+4*mu11**2)] / 2 [E2]
    # Now using tan(2*theta) = 2*tan(theta)/(1-tan(theta)**2) and inserting [E1][E2]
    # We arrive at tan(2*theta) = 2mu11/(mu20-mu02)
    # Hence the definition of the angle below
    M_body = cv2.moments(cv2.threshold(fish_snippet, body_threshold, 255, cv2.THRESH_BINARY)[1])
    angle = 0.5 * np.arctan2(2 * M_body['mu11'], M_body['mu20'] - M_body['mu02'])

    # Second, find the head position by finding the center of mass of thresholded image w/o resizing
    M_head = cv2.moments(fish_snippet)
    x_com = M_head['m10'] / M_head['m00'] - wpx/2
    y_com = M_head['m01'] / M_head['m00'] - hpx/2
    fish_x = cent_x + x_com
    fish_y = cent_y + y_com
    if x_com < 0: # Figure out why this makes sense at some point!
        angle = angle+np.pi

    return fish_x, fish_y, angle, visualization_image, (xpx, ypx, wpx, hpx)