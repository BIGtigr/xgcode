"""
Create and manipulate one dimensional parametric curves.

The one dimensional parametric curves may live in high dimensional space.
The default embedding space is three dimensional Euclidean space.
Everything in the Bezier section assumes that points are numpy arrays.
"""

from collections import defaultdict
from collections import deque
import unittest
import heapq
import math
import itertools

import numpy as np
from scipy import optimize

import bezier
import iterutils

#TODO this could go into the bezier module
class BezierPath:
    """
    This curve is created by patching together cubic Bezier curves.
    It may live in a high dimensional space.
    """
    def __init__(self, bchunks):
        """
        @param bchunks: an iterable of BezierChunk objects
        """
        self.bchunks = list(bchunks)
        self.characteristic_time = None
        self.is_cyclic = False
    def clone(self):
        bchunks = [b.clone() for b in self.bchunks]
        bpath = self.__class__(bchunks)
        bpath.characteristic_time = self.characteristic_time
        bpath.is_cyclic = self.is_cyclic
        return bpath
    def get_start_time(self):
        return self.bchunks[0].start_time
    def get_stop_time(self):
        return self.bchunks[-1].stop_time
    def refine_for_bb(self, abstol=1e-4):
        """
        Chop up the path to tighten the naive bounding box.
        The naive bounding box uses only the bezier
        endpoints and control points.
        This is necessary for drawing into environments like TikZ
        which only use the naive bounding box.
        @param abstol: the axis aligned bounding box should have this error
        """
        for direction in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            self.refine_for_dot(direction, abstol)
    def refine_for_dot(self, direction_in, abstol=1e-4):
        """
        Chop up the path to reduce the dot product towards a direction.
        This is mainly a helper function to help refine
        the path so that the naive bounding box is tight.
        @param direction_in: the direction for the refinement
        @param abstol: the axis aligned bounding box should have this error
        """
        # initialize the direction and the greatest lower bound
        direction = np.array(direction_in)
        glb = None
        # initialize the list of safe bchunks
        safe_bchunks = []
        # initialize the queue
        q = []
        for b in self.bchunks:
            lb, ub = b.get_max_dot_bounds(direction)
            if glb is None or glb < lb:
                glb = lb
            heapq.heappush(q, (-ub, -lb, b))
        # repeatedly refine the queue
        while True:
            # Get the most promising bchunk (the greatest upper bound).
            neg_ub, neg_lb, b = heapq.heappop(q)
            ub, lb = -neg_ub, -neg_lb
            # If the most promising one has a tight bound then we are finished.
            if ub - lb < abstol:
                safe_bchunks.append(b)
                break
            # Bisect the most promising bchunk and look at its pieces.
            for child in b.bisect():
                child_lb, child_ub = child.get_max_dot_bounds(direction)
                # If the child is not promising then leave it out of the queue.
                if child_ub < glb:
                    safe_bchunks.append(child)
                else:
                    # Update the glb and put the child into the queue.
                    if glb < child_lb:
                        glb = child_lb
                    heapq.heappush(q, (-child_ub, -child_lb, child))
        # sort the bchunks by increasing time
        new_bchunks = safe_bchunks + [b for neg_ub, neg_lb, b in q]
        tb_pairs = [(b.start_time, b) for b in new_bchunks]
        self.bchunks = [b for t, b in sorted(tb_pairs)]
    def scale(self, scaling_factor):
        f = lambda p: p*scaling_factor
        self.transform(f)
    def transform(self, f):
        for b in self.bchunks:
            b.transform(f)
    def evaluate(self, t):
        #TODO possibly add a faster function for simultaneous evaluation
        # at multiple times
        for b in self.bchunks:
            if b.start_time <= t <= b.stop_time:
                return b.eval_global(t)
    def get_weak_midpoint_error(self, t_mid, pa, pb):
        p = self.evaluate(t_mid)
        e = np.linalg.norm(p - pa) - np.linalg.norm(pb - p)
        return e*e
    def get_weak_midpoint(self, t_initial, t_final):
        """
        Get a t_mid such that the position is equidistant from the endpoints.
        In other words if c(t) is the curve position at time t,
        then we want a value of t_mid such that
        ||c(t_mid) - c(t_initial)|| == ||c(t_final) - c(t_mid)||.
        Note that this is not necessarily a unique point,
        and it doesn't necessarily have anything to do with arc length.
        @param t_initial: an initial time
        @param t_final: a final time
        @return: t_mid
        """
        args = (self.evaluate(t_initial), self.evaluate(t_final))
        result = scipy.optimize.fminbound(
                self.get_weak_midpoint_error, t_initial, t_final, args)
        return result
    def get_patches(self, times):
        """
        The idea is to patch over the quiescent joints.
        This will erase the small imperfection caused by
        drawing two background-erased curves butted against each other
        or overlapping each other.
        The characteristic times of the returned bpaths should
        be equal to the quiescence time.
        The endpoints of the patches should be halfway between
        the characteristic quiescence time and the neighboring
        intersection times.
        @param times: sorted filtered intersection times
        @return: a collection of BezierPath objects
        """
        # if no quiescence time exists then no patch is needed
        if len(times) < 2:
            return []
        # avoid numerical error at piecewise boundaries
        abstol = 1e-6
        # define the patch endtimes and characteristic times
        patch_triples = []
        for intersect_a, intersect_b in iterutils.pairwise(times):
            tq = 0.5 * (intersect_a + intersect_b)
            ta = (2.0 / 3.0) * intersect_a + (1.0 / 3.0) * intersect_b
            tb = (1.0 / 3.0) * intersect_a + (2.0 / 3.0) * intersect_b
            patch_triples.append((ta, tq, tb))
        # make the patches
        patches = []
        remaining = deque(self.bchunks)
        for ta, tq, tb in patch_triples:
            # chop until we are near time ta
            while remaining[0].start_time < ta - abstol:
                b = remaining.popleft()
                if ta < b.stop_time:
                    ba, bb = b.split_global(ta)
                    remaining.appendleft(bb)
            # eat until we are near time tb
            g = []
            while remaining[0].start_time < tb - abstol:
                b = remaining.popleft()
                if tb < b.stop_time:
                    ba, bb = b.split_global(tb)
                    g.append(ba)
                    remaining.appendleft(bb)
                else:
                    g.append(b)
            # add the patch
            patch = self.__class__(g)
            patch.characteristic_time = tq
            patches.append(patch)
        return patches
    #TODO finish or remove _cyclic_shatter
    def _cyclic_shatter(self, times):
        """
        Return a collection of BezierPath objects.
        The returned objects should be annotated
        with characteristic times corresponding to intersections.
        @param times: sorted filtered intersection times
        @return: a collection of BezierPath objects
        """
        # Handle the edge case of no intersections.
        if not times:
            self.characteristic_time = 0.5 * (
                    self.get_start_time() + self.get_stop_time())
            return [self]
        # If there is a single intersection
        # then break the cycle at the opposite time.
        return
    def shatter(self, times):
        """
        Return a collection of BezierPath objects.
        The returned objects should be annotated
        with characteristic times corresponding to intersections.
        @param times: sorted filtered intersection times
        @return: a collection of BezierPath objects
        """
        # handle the edge case of no intersections
        if not times:
            self.characteristic_time = 0.5 * (
                    self.get_start_time() + self.get_stop_time())
            return [self]
        # handle the edge case of a single intersection
        if len(times) == 1:
            self.characteristic_time = times[0]
            return [self]
        # Compute quiescence times.
        # TODO use weak spatially quiescent midpoints
        # instead of naive temporally quiescent midpoints
        quiescence_times = [0.5*(a+b) for a, b in iterutils.pairwise(times)]
        # Construct the bchunks sequences.
        # Use whole bchunks when possible,
        # but at quiescence times we might have to split the bchuncks.
        remaining = deque(self.bchunks)
        groups = []
        g = []
        # repeatedly split the remaining sequence
        for q in quiescence_times:
            while True:
                b = remaining.popleft()
                if b.start_time <= q <= b.stop_time:
                    ba, bb = b.split_global(q)
                    g.append(ba)
                    remaining.appendleft(bb)
                    groups.append(g)
                    g = []
                    break
                else:
                    g.append(b)
        g.extend(remaining)
        groups.append(g)
        # Create a piecewise bezier curve from each group,
        # and give each piecewise curve a characteristic time.
        piecewise_curves = []
        for t, group in zip(times, groups):
            curve = self.__class__(group)
            curve.characteristic_time = t
            piecewise_curves.append(curve)
        return piecewise_curves

def get_bezier_path(fp, fv, t_initial, t_final, nchunks):
    """
    @param fp: a python function from t to position vector
    @param fv: a python function from t to velocity vector
    @param t_initial: initial time
    @param t_final: final time
    @param nchunks: use this many chunks in the piecewise approximation
    @return: a BezierPath
    """
    bchunks = []
    npoints = nchunks + 1
    duration = t_final - t_initial
    incr = duration / nchunks
    times = [t_initial + i*incr for i in range(npoints)]
    for ta, tb in iterutils.pairwise(times):
        b = bezier.create_bchunk_hermite(
                ta, tb, fp(ta), fp(tb), fv(ta), fv(tb))
        bchunks.append(b)
    return BezierPath(bchunks)



#FIXME this function is a linear piecewise holdout that does not use bezier
def get_piecewise_curve(f, t_initial, t_final, npieces_min, seg_length_max):
    """
    Convert a parametric curve into a collection of line segments.
    @param f: returns the (x, y, z) value at time t
    @param t_initial: initial value of t
    @param t_final: final value of t
    @param npieces_min: minimum number of line segments
    @param seg_length_max: maximum line segment length without subdivision
    """
    # define a heap of triples (-length, ta, tb)
    # where length is ||f(tb) - f(ta)||
    q = []
    # initialize the heap
    t_incr = float(t_final - t_initial) / npieces_min
    for i in range(npieces_min):
        ta = t_initial + t_incr * i
        tb = ta + t_incr
        dab = np.linalg.norm(f(tb) - f(ta))
        heapq.heappush(q, (-dab, ta, tb))
    # While segments are longer than the max allowed length,
    # subdivide the segments.
    while -q[0][0] > seg_length_max:
        neg_d, ta, tc = heapq.heappop(q)
        tb = float(ta + tc) / 2
        dab = np.linalg.norm(f(tb) - f(ta))
        dbc = np.linalg.norm(f(tc) - f(tb))
        heapq.heappush(q, (-dab, ta, tb))
        heapq.heappush(q, (-dbc, tb, tc))
    # convert time segments to spatial segments
    return [(f(ta), f(tb)) for neg_d, ta, tb in q]


class OrthoCircle:
    def __init__(self, center, radius, axis):
        """
        @param center: a 3d point
        @param radius: a scalar radius
        @param axis: one of {0, 1, 2}
        """
        self.center = center
        self.radius = radius
        self.axis = axis
    def __call__(self, t):
        """
        @param t: a float in the interval [0, 1]
        @return: a 3d point
        """
        p = np.zeros(3)
        axis_a = (self.axis + 1) % 3
        axis_b = (self.axis + 2) % 3
        theta = 2 * math.pi * t
        p[axis_a] = self.radius * math.cos(theta)
        p[axis_b] = self.radius * math.sin(theta)
        return p + self.center

class LineSegment:
    def __init__(self, initial_point, final_point):
        """
        @param initial_point: the first point of the line segment
        @param final_point: the last point of the line segment
        """
        self.initial_point = initial_point
        self.final_point = final_point
    def __call__(self, t):
        """
        @param t: a float in the interval [0, 1]
        @return: a 3d point
        """
        return self.initial_point * (1-t) + self.final_point * t

