import cv2 as cv
import numpy as np

# ------------------------------------------------------------------
# 1) Paste the MATLAB numbers here
# ------------------------------------------------------------------
a0, a2, a3, a4  = 684.0465, -0.0017, 0.0, 0.0     # MappingCoefficients
cx, cy          = 976.0474, 521.8287              # DistortionCenter
stretch         = np.eye(2)                       # StretchMatrix
img_h, img_w    = 1080, 1920                      # ImageSize (rows, cols)
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# 2) helper:  ρ  ->  f(ρ)   and Newton solver for ρ
# ------------------------------------------------------------------
def f_r(r):
    return a0 + a2*r**2 + a3*r**3 + a4*r**4

def df_r(r):
    return 2*a2*r + 3*a3*r**2 + 4*a4*r**3

def solve_r(s):
    """
    solves  r - s*f(r) = 0   for r  (Newton)
    s >= 0  is the slope  √(dx²+dy²)/dz
    """
    if s == 0:                               # exactly the optical axis
        return 0.0
    r = a0 * s                               # good initial guess
    for _ in range(5):                       # 5 iterations are enough
        g  = r - s*f_r(r)
        dg = 1 - s*df_r(r)
        r -= g/dg
    return r
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# 3) build one remap table for a **perspective** view
# ------------------------------------------------------------------
def build_remap(out_w=1280, out_h=720, fov_deg=100):
    """
    Return two float32 maps usable by cv.remap().  The output camera is a
    simple pin-hole camera with horizontal FOV = `fov_deg`.
    """
    fx = out_w / (2*np.tan(np.deg2rad(fov_deg)/2))
    fy = fx
    cx_p, cy_p = out_w/2, out_h/2

    j, i = np.meshgrid(np.arange(out_w), np.arange(out_h))  # pixel grid
    x = (j - cx_p) / fx
    y = (i - cy_p) / fy
    z = np.ones_like(x)

    r_slope = np.sqrt(x*x + y*y) / z                       # s in the text
    r = np.vectorize(solve_r)(r_slope)                     # numeric root
    fr = f_r(r)

    u = x * fr / z
    v = y * fr / z

    map_x = (stretch[0,0]*u + stretch[0,1]*v + cx).astype(np.float32)
    map_y = (stretch[1,0]*u + stretch[1,1]*v + cy).astype(np.float32)
    return map_x, map_y

map1, map2 = build_remap(out_w=1280, out_h=720, fov_deg=110)
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# 4) run live
# ------------------------------------------------------------------
cap = cv.VideoCapture(0)                    # ← change to your source
if not cap.isOpened():
    raise IOError("Cannot open camera")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    # NOTE: frame must be 1920×1080.  If your camera is different, resize
    # or adapt MappingCoefficients accordingly.
    frame = cv.resize(frame, (img_w, img_h), interpolation=cv.INTER_AREA)

    undist = cv.remap(frame, map1, map2, interpolation=cv.INTER_LINEAR,
                      borderMode=cv.BORDER_CONSTANT)

    cv.imshow('raw',       frame)
    cv.imshow('undistort', undist)
    if cv.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv.destroyAllWindows()