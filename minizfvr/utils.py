import numpy as np
import re
import cv2
from PyQt5.QtWidgets import (
    QLineEdit,
    QPushButton,
    QLabel
)
from PyQt5.QtCore import pyqtSignal, QSize
from PyQt5.QtGui import QWheelEvent, QIcon
from pathlib import Path

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

def encode_frame_to_array(img, arr):
    """
    Given an image and 1d array, ravel image and put it in the array
    Expect array to be based off of shared memory
    This mutates the content of arr
    """
    arr[:img.size] = img.ravel()
    arr[-4] = img.shape[0] // 255
    arr[-3] = img.shape[0] % 255
    arr[-2] = img.shape[1] // 255
    arr[-1] = img.shape[1] % 255
    return arr

def decode_array_to_frame(arr):
    """
    Given a 1D-array of uint8 created with the above encode_frame_to_array function,
    reconstitute an image
    """
    frame_shape = (int(arr[-4]) * 255 + int(arr[-3]),
                   int(arr[-2]) * 255 + int(arr[-1]))
    return arr[:frame_shape[0] * frame_shape[1]].reshape(frame_shape)


class TypeForcedEdit(QLineEdit):
    """
    Type-checking numeric entries in upper layers is stupid so we subclass LineEdit
    """
    def __init__(self, forced_type: type, scroll_step=None):
        super().__init__()
        self.val = None
        self.forced_type = forced_type

        # We implement wheelEvent so we can scroll to change values
        # We need to adjust the amount of change per one wheel tick
        if not scroll_step:  # default
            self.scroll_step = forced_type(1.0)  # cast
        else:
            self.scroll_step = forced_type(scroll_step)

        # Every time we type in new values, we make sure they conform to whatever type we expect
        # otherwise we keep the old value
        self.editingFinished.connect(self._force_type)

    def setValue(self, val):
        """
        This is used to set a new value from the program
        """
        try:
            fval = self.forced_type(val) # cast
            self.val = fval
            self.setText(str(fval))
        except:
            # It is very unlikely we reach here
            print('cannot cast the programmatically set new value into type:', self.forced_type)

    def _force_type(self):
        """
        A callback function after edit finish
        """
        new_text = self.text()
        try:
            casted = self.forced_type(new_text)
            self.val = casted
            self.setText(str(self.val))
        except:
            print('cannot cast the input into type:', self.forced_type)

    def value(self):
        """
        Static method, so it will behave similarly to sliders etc.
        """
        return self.val

    def wheelEvent(self, event: QWheelEvent):
        """
        Add scroll behavior for easier interactive control of numeric values
        In a typical mouse while, one tick corresponds to 15 degrees, which is 120 angleDelta (in int)
        """

        # get how many ticks we moved
        # we cast to float, just in case we happen to have a mouse with a finer reso wheel
        tick_delta = float(event.angleDelta().y()) / 120.0
        self.setValue(self.val + tick_delta * self.scroll_step)  # casting happens inside
        self.editingFinished.emit()


class bistateButton(QPushButton):
    """
    Push button that flips state when clicked
    """

    def __init__(self, *args, t2='', c1='white', c2='red'):
        super().__init__(*args)
        self.t1 = self.text()
        self.t2 = t2
        self.activated = False
        self.original_color = c1
        self.activated_color = c2
        self.user_defined_stylesheet = self.styleSheet()

    def force_state(self, state):
        """
        Force true or false state
        """
        self.activated = state
        if self.activated:
            self.setText(self.t2)
            self.setStyleSheet(self.user_defined_stylesheet + 'color: {};'.format(self.activated_color))
        else:
            self.setText(self.t1)
            self.setStyleSheet(self.user_defined_stylesheet + 'color: {};'.format(self.original_color))

    def switch_state(self):
        """
        Flip the state (convenient for callback)
        """
        self.force_state(not self.activated)

    def setStyleSheet(self, sh):
        """
        I will keep style sheet as a str, because I don't want to keep appending
        stuff every time I toggle the button state
        """
        super().setStyleSheet(sh)
        self.user_defined_stylesheet = self.styleSheet()

class roundButton(QLabel):
    """
    For the stimulus window, we do not want the titlebar to be showing because it can be bright
    Instead, we will show a subtle round icon, based on LineEdit
    """

    clicked = pyqtSignal() # make it clickable

    def __init__(self, *args, color_rgb=(255, 0, 0), radius=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.color_rgb = color_rgb
        self.radius = radius
        self.resize(radius*2, radius*2)
        self.changeAlpha(30)

    def changeAlpha(self, alpha):
        self.setStyleSheet(
            """
            text-align: center;
            background-color: rgba({0}, {1}, {2}, {3}%);
            border-radius: {4}px;
            """.format(*self.color_rgb, alpha, self.radius)
        )

    def mousePressEvent(self, e):
        self.clicked.emit()

    def enterEvent(self, *args, **kwargs):
        """
        The button becomes opaque on hover
        """
        self.changeAlpha(100)

    def leaveEvent(self, *args, **kwargs):
        self.changeAlpha(30)

def sync_buffer_to_file(file, buffer, last_sample_index, buffer_size):
    """
    Copy last n_sample datapoints from buffer (dict of arrays) to file (h5py.File with Datasets matching the buffer)
    """
    n_sample = last_sample_index % buffer_size
    # if the last_sample_index is cleanly divided by the buffer size and we are calling this function, it means
    # that the entire buffer is the new, un-saved data
    if n_sample == 0:
        n_sample = buffer_size
    for var in buffer.keys():
        file[var][(last_sample_index-n_sample):last_sample_index] = buffer[var][:n_sample]



def parse_glsl(text, qualifier):
    """
    To make shader inputs a bit more accessible, we parse glsl code to find variables with a specified qualifier
    """
    out = []
    # we can have None shader for geometry shader, so we check for that here
    if text is not None:
        # parse lines with line break and semicolons
        lines = re.split('\n|;', text)
        for line in lines:
            # parse words by space
            words = re.split('\s', line)
            if words[0] == qualifier:

                # With an assumption that we are never going to pass matrices as inputs, I look for numbers in the
                # type name (like vec2 or vec3), and count up these numbers to derive the shape of inputs.
                temp = re.search('[0-9]+', words[1])
                if temp is None:
                    var_length = 1
                else:
                    var_length = int(temp.group())

                out.append((words[2], var_length))
    return out

def set_icon(widget):
    """
    Set icon to widgets
    """
    app_icon = QIcon()  # a holder for icons
    for size in [32, 64, 128]:
        app_icon.addFile(str(Path(__file__).resolve().parent / 'assets' / 'icon_{}.png'.format(size)),
                         QSize(size, size))
    widget.setWindowIcon(app_icon)