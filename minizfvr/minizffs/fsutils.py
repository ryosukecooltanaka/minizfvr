import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment as LSA
from time import time

def detect_fish(img, bg, image_scale, dilate_size, color_invert, body_threshold, real_fish_px_range, n_fish_to_track):
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

    # Detect fish as a connected region with the N largest among ones with appropriate size
    n_labels, _, stats, centroids = cv2.connectedComponentsWithStats(body_img)

    is_appropriate_size = (stats[:,-1] > real_fish_px_range[0]) * (stats[:,-1] < real_fish_px_range[1])
    n_detected_fish_like_object = np.sum(is_appropriate_size)
    n_fish_to_report = min(n_detected_fish_like_object, n_fish_to_track)

    # nothing found
    if not any(is_appropriate_size):
        # There will always be at least one label (i.e., background)
        # If we cannot find the fish body, we will just return nan
            return [], [], [], visualization_image, ([],)*4
    
    # cent_x, cent_y etc. are 1d array with the length of n_fish_to_report
    fish_ids = np.argsort(-stats[:, -1]*is_appropriate_size)[:n_fish_to_report]
    cent_x, cent_y = centroids[fish_ids, :].T / image_scale # we will always operate in the px coordinate of the original frame

    # slice fish
    xpx, ypx, wpx, hpx, _ = (stats[fish_ids, :].T / image_scale).astype(int)

    # Now we loop over each fish
    x_com, y_com, angle = np.zeros(n_fish_to_report), np.zeros(n_fish_to_report), np.zeros(n_fish_to_report)
    for i in range(n_fish_to_report):

        # cut out the area round the fish
        fish_snippet = diff_img[ypx[i]:(ypx[i]+hpx[i]), xpx[i]:(xpx[i]+wpx[i])]

        # update the viusalization image
        slice_y = slice(int(ypx[i]*image_scale), int((ypx[i]+hpx[i])*image_scale))
        slice_x = slice(int(xpx[i]*image_scale), int((xpx[i]+wpx[i])*image_scale))
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
        angle[i] = 0.5 * np.arctan2(2 * M_body['mu11'], M_body['mu20'] - M_body['mu02'])

        # Second, find the head position by finding the center of mass of thresholded image w/o resizing
        M_head = cv2.moments(fish_snippet)
        x_com[i] = M_head['m10'] / M_head['m00'] - wpx[i]/2
        y_com[i] = M_head['m01'] / M_head['m00'] - hpx[i]/2

    fish_x = cent_x + x_com
    fish_y = cent_y + y_com
    
    angle[x_com<0] += np.pi

    return fish_x, fish_y, angle, visualization_image, (xpx, ypx, wpx, hpx)

def solve_fish_correspondence(x, y, theta, t, max_velocity_mms=50):
    """
    Solve fish correspondence with the Hungarian algorithm.
    Use squared distance as the cost value, and when there is 
    missing values, we use fixed cost derived from maximum velocity.
    If we trust theta enough, in principle we can use that as cost as well.
    """

    # we assume x, y, theta to be timepoint x n_fish matrix and x/y in mm
    sorted_x = [x[0]]
    sorted_y = [y[0]]
    sorted_theta = [theta[0]]

    print('Solving correspondence among {1} fish for {0} frames'.format(*x.shape))
    index_to_report_progress = np.arange(0, len(t), len(t)//10).astype(int)

    tic = time()
    for i in range(1,len(t)):
        # calculate squared distance
        DD = (sorted_x[-1][:,None]-x[i][None,:])**2 + (sorted_y[-1][:,None]-y[i][None,:])**2
        # get the duration
        dt = t[i]-t[i-1]
        # maximum possible squared distance fish can move (say 50 mm/s)
        max_dd = (max_velocity_mms*dt)**2
        # penalize missing value with this max squared distance
        DD[np.isnan(DD)] = max_dd
        # solve correspondence with the Hungarian algorithm
        _, sort_ind = LSA(DD)
        sorted_x.append(x[i][sort_ind])
        sorted_y.append(y[i][sort_ind])
        sorted_theta.append(theta[i][sort_ind])
        
        if any(index_to_report_progress==i):
            print('Done {0:0.2f}%'.format(100*i/len(t)))
    print('Finished solving correspondence! Took {0:0.2f} s'.format(time()-tic))

    
    sorted_x = np.asarray(sorted_x)
    sorted_y = np.asarray(sorted_y)
    sorted_theta = np.asarray(sorted_theta)

    return sorted_x, sorted_y, sorted_theta
