import numpy as np
import cv2

def center_of_mass_based_tracking(img, base, tip, n_seg, search_radius):
    """
    Reimplementation of the center-of-mass based tail tracking in the stytra.
    Given the resting state linear guess of the tail position specified by base/tip (2 tuples (x, y)),
    each segment is assigned a fixed length of (tip - base) / n_seg.
    For each segment, we calculate pixel intensity center-of-mass around the guessed segment-tip, which is defined by
    the current segment base and the direction of the previous segment times the segment length. We then consider
    a half-line from the current segment base through the calculated center-of-mass, and the point on this line
    that is the fixed segment length away from the segment base would be the current segment tip.
    This current segment tip will be the base of the next segment, and the direction of this segment will again
    serve as the initial guess of the next segment.
    """

    total_length = np.sqrt((tip[0]-base[0])**2 + (tip[1]-base[1])**2)
    seg_length = total_length / n_seg

    # redefine base position and displacements as something that can be updated
    bx, by = base
    dx = (tip[0] - bx) / n_seg
    dy = (tip[1] - by) / n_seg

    # store results
    angles = np.full(n_seg, np.nan)
    segments = np.full((2, n_seg + 1), np.nan)
    segments[:, 0] = base
    # iteratively call the tip finding function

    for i in range(n_seg):
        bx, by, dx, dy = find_tip_with_com(img, bx, by, dx, dy, seg_length, search_radius)
        # tip finding function will return negative bx if there is anything wrong
        if bx<0:
            break
        angles[i] = np.arctan2(dx, dy)
        segments[:, i+1] = (bx, by)

    return segments, angles


def find_tip_with_com(image, bx, by, dx, dy, lseg, radius):
    """
    Given the base of the current segment and the guessed location of its tip,
    calculate the image intensity center-of-mass (COM) around this guessed point,
    and define the tip as the point on the base-to-COM line with the distance
    pre-determined by the segment length.
    """

    # First, prepare integer indices to define the area within which we calculate COM
    x0 = int(np.clip(bx + dx - radius, 0, image.shape[1]))
    x1 = int(np.clip(bx + dx + radius, 0, image.shape[1]))
    y0 = int(np.clip(by + dy - radius, 0, image.shape[0]))
    y1 = int(np.clip(by + dy + radius, 0, image.shape[0]))

    # return invalid values if the area is entirely outside the image
    if x0 == x1 and y0 == y1:
        return -1, -1, 0, 0

    # loop through all pixels in [x0, x1], [y0, y1] and calculate the product of the position & intensity
    # the stytra version used loop and numba.njit -- I think numpy is faster or equivalent
    XX, YY = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
    in_radius_mask = ((XX-(bx+dx))**2 + (YY-(by+dy))**2) <= radius**2
    search_slice = image[y0:y1, :][:, x0:x1]
    total_intensity = np.sum(in_radius_mask * search_slice)
    summed_ix = np.sum(in_radius_mask * XX * search_slice)
    summed_iy = np.sum(in_radius_mask * YY * search_slice)

    # if no pixel has positive value wihthin the search area, we return error (negative base_x)
    if total_intensity == 0.0:
        return -1, -1, 0, 0

    # get the COM (this is in the absolute pixel coordinate)
    com_x = summed_ix / total_intensity
    com_y = summed_iy / total_intensity

    # now, calculate new dx/dy by forcing the pre-defined segment legnth
    length_ratio = lseg / np.sqrt((com_x - bx) ** 2 + (com_y - by) ** 2)
    new_dx = (com_x - bx) * length_ratio
    new_dy = (com_y - by) * length_ratio

    # return values can be exactly interpreted as base_x/y, dx/y for the next iteration
    return bx + new_dx, by + new_dy, new_dx, new_dy

def preprocess_image(img, image_scale=1, filter_size=3, color_invert=False, clip_threshold=0, **kwargs):
    """
    Image preprocessing for tail tracking, as in stytra
    cv2 is precompiled and is very fast
    """
    if image_scale != 1:
        img = cv2.resize(img, None, fx=image_scale, fy=image_scale, interpolation=cv2.INTER_AREA)
    if filter_size > 1:
        img = cv2.boxFilter(img, -1, (filter_size, filter_size))
    if color_invert:
        img = 255 - img
    if clip_threshold > 0:
        img = (255-clip_threshold) - cv2.threshold(src=255-img, thresh=255-clip_threshold, type=cv2.THRESH_TRUNC, maxval=255)[1]

    return img