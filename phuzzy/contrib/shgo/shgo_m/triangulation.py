import numpy
import copy

try:
    from functools import lru_cache  # For Python 3 only
except ImportError:  # Python 2:
    import time
    import functools
    import collections

    # Note to avoid using external packages such as functools32 we use this code
    # only using the standard library
    def lru_cache(maxsize=255, timeout=None):
        """
        Thanks to ilialuk @ https://stackoverflow.com/users/2121105/ilialuk for
        this code snippet. Modifications by S. Endres
        """

        class LruCacheClass(object):
            def __init__(self, input_func, max_size, timeout):
                self._input_func = input_func
                self._max_size = max_size
                self._timeout = timeout

                # This will store the cache for this function,
                # format - {caller1 : [OrderedDict1, last_refresh_time1],
                #  caller2 : [OrderedDict2, last_refresh_time2]}.
                #   In case of an instance method - the caller is the instance,
                # in case called from a regular function - the caller is None.
                self._caches_dict = {}

            def cache_clear(self, caller=None):
                # Remove the cache for the caller, only if exists:
                if caller in self._caches_dict:
                    del self._caches_dict[caller]
                    self._caches_dict[caller] = [collections.OrderedDict(),
                                                 time.time()]

            def __get__(self, obj, objtype):
                """ Called for instance methods """
                return_func = functools.partial(self._cache_wrapper, obj)
                return_func.cache_clear = functools.partial(self.cache_clear,
                                                            obj)
                # Return the wrapped function and wraps it to maintain the
                # docstring and the name of the original function:
                return functools.wraps(self._input_func)(return_func)

            def __call__(self, *args, **kwargs):
                """ Called for regular functions """
                return self._cache_wrapper(None, *args, **kwargs)

            # Set the cache_clear function in the __call__ operator:
            __call__.cache_clear = cache_clear

            def _cache_wrapper(self, caller, *args, **kwargs):
                # Create a unique key including the types (in order to
                # differentiate between 1 and '1'):
                kwargs_key = "".join(map(
                    lambda x: str(x) + str(type(kwargs[x])) + str(kwargs[x]),
                    sorted(kwargs)))
                key = "".join(
                    map(lambda x: str(type(x)) + str(x), args)) + kwargs_key

                # Check if caller exists, if not create one:
                if caller not in self._caches_dict:
                    self._caches_dict[caller] = [collections.OrderedDict(),
                                                 time.time()]
                else:
                    # Validate in case the refresh time has passed:
                    if self._timeout is not None:
                        if (time.time() - self._caches_dict[caller][1]
                                > self._timeout):
                            self.cache_clear(caller)

                # Check if the key exists, if so - return it:
                cur_caller_cache_dict = self._caches_dict[caller][0]
                if key in cur_caller_cache_dict:
                    return cur_caller_cache_dict[key]

                # Validate we didn't exceed the max_size:
                if len(cur_caller_cache_dict) >= self._max_size:
                    # Delete the first item in the dict:
                    try:
                        cur_caller_cache_dict.popitem(False)
                    except KeyError:
                        pass
                # Call the function and store the data in the cache (call it
                # with the caller in case it's an instance function
                # - Ternary condition):
                cur_caller_cache_dict[key] = self._input_func(caller, *args,
                                                              **kwargs) if caller is not None else self._input_func(
                    *args, **kwargs)
                return cur_caller_cache_dict[key]

        # Return the decorator wrapping the class (also wraps the instance to
        # maintain the docstring and the name of the original function):
        return (lambda input_func: functools.wraps(input_func)(
            LruCacheClass(input_func, maxsize, timeout)))


class Complex:
    def __init__(self, dim, func, func_args=(), symmetry=False, bounds=None,
                 g_cons=None, g_args=()):
        self.dim = dim
        self.bounds = bounds
        self.symmetry = symmetry  # TODO: Define the functions to be used
        #      here in init to avoid if checks
        self.gen = 0
        self.perm_cycle = 0

        # Every cell is stored in a list of its generation,
        # ex. the initial cell is stored in self.H[0]
        # 1st get new cells are stored in self.H[1] etc.
        # When a cell is subgenerated it is removed from this list

        self.H = []  # Storage structure of cells
        # Cache of all vertices
        self.V = VertexCache(func, func_args, bounds, g_cons, g_args)

        # Generate n-cube here:
        self.n_cube(dim, symmetry=symmetry)

        # TODO: Assign functions to a the complex instead
        if symmetry:
            pass
            self.generation_cycle = 1
            # self.centroid = self.C0()[-1].x
            # self.C0.centroid = self.centroid
        else:
            self.add_centroid()

        self.H.append([])
        self.H[0].append(self.C0)
        self.hgr = self.C0.homology_group_rank()
        self.hgrd = 0  # Complex group rank differential
        # self.hgr = self.C0.hg_n

        # Build initial graph
        self.graph_map()

        self.performance = []
        self.performance.append(0)
        self.performance.append(0)

    def __call__(self):
        return self.H

    def n_cube(self, dim, symmetry=False, printout=False):
        """
        Generate the simplicial triangulation of the n dimensional hypercube
        containing 2**n vertices
        """
        import numpy
        origin = list(numpy.zeros(dim, dtype=int))
        self.origin = origin
        supremum = list(numpy.ones(dim, dtype=int))
        self.suprenum = supremum

        x_parents = []
        x_parents.append(tuple(self.origin))

        if symmetry:
            # self.C0 = Cell(0, 0, 0, self.origin, self.suprenum)
            self.C0 = Simplex(0, 0, 0, 0, self.dim)  # Initial cell object
            self.C0.add_vertex(self.V[tuple(origin)])

            i_s = 0
            self.perm_symmetry(i_s, x_parents, origin)
            self.C0.add_vertex(self.V[tuple(supremum)])
        else:
            self.C0 = Cell(0, 0, 0, self.origin,
                           self.suprenum)  # Initial cell object
            self.C0.add_vertex(self.V[tuple(origin)])
            self.C0.add_vertex(self.V[tuple(supremum)])

            i_parents = []
            self.perm(i_parents, x_parents, origin)

        if printout:
            print("Initial hyper cube:")
            for v in self.C0():
                print(self.C0())
                print("Vertex: {}".format(v.x))
                print("v.f: {}".format(v.f))
                constr = 'Connections: '
                for vc in v.nn:
                    constr += '{} '.format(vc.x)

                print(constr)
                print('Order = {}'.format(v.order))

    def perm(self, i_parents, x_parents, xi):
        # TODO: Cut out of for if outside linear constraint cutting planes
        xi_t = tuple(xi)

        # Construct required iterator
        iter_range = [x for x in range(self.dim) if x not in i_parents]

        for i in iter_range:
            i2_parents = copy.copy(i_parents)
            i2_parents.append(i)
            xi2 = copy.copy(xi)
            xi2[i] = 1
            # Make new vertex list a hashable tuple
            xi2_t = tuple(xi2)
            # Append to cell
            self.C0.add_vertex(self.V[xi2_t])
            # Connect neighbours and vice versa
            # Parent point
            self.V[xi2_t].connect(self.V[xi_t])

            # Connect all family of simplices in parent containers
            for x_ip in x_parents:
                self.V[xi2_t].connect(self.V[x_ip])

            x_parents2 = copy.copy(x_parents)
            x_parents2.append(xi_t)

            # Permutate
            self.perm(i2_parents, x_parents2, xi2)

    def perm_symmetry(self, i_s, x_parents, xi):
        # TODO: Cut out of for if outside linear constraint cutting planes
        xi_t = tuple(xi)
        xi2 = copy.copy(xi)
        xi2[i_s] = 1
        # Make new vertex list a hashable tuple
        xi2_t = tuple(xi2)
        # Append to cell
        self.C0.add_vertex(self.V[xi2_t])
        # Connect neighbours and vice versa
        # Parent point
        self.V[xi2_t].connect(self.V[xi_t])

        # Connect all family of simplices in parent containers
        for x_ip in x_parents:
            self.V[xi2_t].connect(self.V[x_ip])

        x_parents2 = copy.copy(x_parents)
        x_parents2.append(xi_t)

        i_s += 1
        if i_s == self.dim:
            return
        # Permutate
        self.perm_symmetry(i_s, x_parents2, xi2)

    def add_centroid(self):
        """Split the central edge between the origin and suprenum of
        a cell and add the new vertex to the complex"""
        self.centroid = list(
            (numpy.array(self.origin) + numpy.array(self.suprenum)) / 2.0)
        self.C0.add_vertex(self.V[tuple(self.centroid)])
        self.C0.centroid = self.centroid

        if 0:  # Constrained centroid
            v_sum = 0
            for v in self.C0():
                v_sum += numpy.array(v.x)

            self.centroid = list(v_sum / len(self.C0()))
            self.C0.add_vertex(self.V[tuple(self.centroid)])
            self.C0.centroid = self.centroid

        # Disconnect origin and suprenum
        self.V[tuple(self.origin)].disconnect(self.V[tuple(self.suprenum)])

        # Connect centroid to all other vertices
        for v in self.C0():
            self.V[tuple(self.centroid)].connect(self.V[tuple(v.x)])

        self.centroid_added = True
        return

    # Construct incidence array:
    def incidence(self):
        if self.centroid_added:
            self.structure = numpy.zeros([2 ** self.dim + 1, 2 ** self.dim + 1],
                                         dtype=int)
        else:
            self.structure = numpy.zeros([2 ** self.dim, 2 ** self.dim],
                                         dtype=int)

        for v in self.HC.C0():
            for v2 in v.nn:
                # self.structure[0, 15] = 1
                self.structure[v.Ind, v2.Ind] = 1

        return

    # A more sparse incidence generator:
    def graph_map(self):
        """ Make a list of size 2**n + 1 where an entry is a vertex
        incidence, each list element contains a list of indexes
        corresponding to that entries neighbours"""

        self.graph = [[v2.Ind for v2 in v.nn] for v in self.C0()]

    # Graph structure method:
    # 0. Capture the indices of the initial cell.
    # 1. Generate new origin and suprenum scalars based on current generation
    # 2. Generate a new set of vertices corresponding to a new
    #    "origin" and "suprenum"
    # 3. Connected based on the indices of the previous graph structure
    # 4. Disconnect the edges in the original cell

    def sub_generate_cell(self, C_i, gen):
        """Subgenerate a cell `C_i` of generation `gen` and
        homology group rank `hgr`."""
        origin_new = tuple(C_i.centroid)
        centroid_index = len(C_i()) - 1

        # If not gen append
        try:
            self.H[gen]
        except IndexError:
            self.H.append([])

        # Generate subcubes using every extreme vertex in C_i as a suprenum
        # and the centroid of C_i as the origin
        H_new = []  # list storing all the new cubes split from C_i
        for i, v in enumerate(C_i()[:-1]):
            suprenum = tuple(v.x)
            H_new.append(
                self.construct_hypercube(origin_new, suprenum,
                                         gen, C_i.hg_n, C_i.p_hgr_h))

        for i, connections in enumerate(self.graph):
            # Present vertex V_new[i]; connect to all connections:
            if i == centroid_index:  # Break out of centroid
                break

            for j in connections:
                C_i()[i].disconnect(C_i()[j])

        # Destroy the old cell
        if C_i is not self.C0:  # Garbage collector does this anyway; not needed
            del (C_i)

        # TODO: Recalculate all the homology group ranks of each cell
        return H_new

    def split_generation(self):
        """
        Run sub_generate_cell for every cell in the current complex self.gen
        """
        no_splits = False  # USED IN SHGO
        try:
            for c in self.H[self.gen]:
                if self.symmetry:
                    # self.sub_generate_cell_symmetry(c, self.gen + 1)
                    self.split_simplex_symmetry(c, self.gen + 1)
                else:
                    self.sub_generate_cell(c, self.gen + 1)
        except IndexError:
            no_splits = True  # USED IN SHGO

        self.gen += 1
        return no_splits  # USED IN SHGO

    # @lru_cache(maxsize=None)
    def construct_hypercube(self, origin, suprenum, gen, hgr, p_hgr_h,
                            printout=False):
        """
        Build a hypercube with triangulations symmetric to C0.

        Parameters
        ----------
        origin : vec
        suprenum : vec (tuple)
        gen : generation
        hgr : parent homology group rank
        """

        # Initiate new cell
        C_new = Cell(gen, hgr, p_hgr_h, origin, suprenum)
        C_new.centroid = tuple(
            (numpy.array(origin) + numpy.array(suprenum)) / 2.0)
        # C_new.centroid =

        # centroid_index = len(self.C0()) - 1
        # Build new indexed vertex list
        V_new = []

        # Cached calculation
        for i, v in enumerate(self.C0()[:-1]):
            t1 = self.generate_sub_cell_t1(origin, v.x)
            t2 = self.generate_sub_cell_t2(suprenum, v.x)

            vec = t1 + t2

            vec = tuple(vec)
            C_new.add_vertex(self.V[vec])
            V_new.append(vec)

        # Add new centroid
        C_new.add_vertex(self.V[C_new.centroid])
        V_new.append(C_new.centroid)

        # Connect new vertices #TODO: Thread into other loop; no need for V_new
        for i, connections in enumerate(self.graph):
            # Present vertex V_new[i]; connect to all connections:
            for j in connections:
                self.V[V_new[i]].connect(self.V[V_new[j]])

        if printout:
            print("A sub hyper cube with:")
            print("origin: {}".format(origin))
            print("suprenum: {}".format(suprenum))
            for v in C_new():
                print("Vertex: {}".format(v.x))
                constr = 'Connections: '
                for vc in v.nn:
                    constr += '{} '.format(vc.x)

                print(constr)
                print('Order = {}'.format(v.order))

        # Append the new cell to the to complex
        self.H[gen].append(C_new)

        return C_new

    def split_simplex_symmetry(self, S, gen):
        """
        Split a hypersimplex S into two sub simplcies by building a hyperplane
        which connects to a new vertex on an edge (the longest edge in
        dim = {2, 3}) and every other vertex in the simplex that is not
        connected to the edge being split.

        This function utilizes the knowledge that the problem is specified
        with symmetric constraints

        The longest edge is tracked by an ordering of the
        vertices in every simplices, the edge between first and second
        vertex is the longest edge to be split in the next iteration.
        """
        # If not gen append
        try:
            self.H[gen]
        except IndexError:
            self.H.append([])
        # gen, hgr, p_hgr_h,
        # gen, C_i.hg_n, C_i.p_hgr_h

        # Find new vertex.
        # V_new_x = tuple((numpy.array(C()[0].x) + numpy.array(C()[1].x)) / 2.0)
        V_new = self.V[
            tuple((numpy.array(S()[0].x) + numpy.array(S()[-1].x)) / 2.0)]

        # Disconnect old longest edge
        self.V[S()[0].x].disconnect(self.V[S()[-1].x])

        # Connect new vertices to all other vertices
        for v in S()[:]:
            v.connect(self.V[V_new.x])

        # New "lower" simplex
        S_new_l = Simplex(gen, S.hg_n, S.p_hgr_h, self.generation_cycle,
                          self.dim)
        S_new_l.add_vertex(S()[0])
        S_new_l.add_vertex(V_new)  # Add new vertex
        for v in S()[1:-1]:  # Add all other vertices
            S_new_l.add_vertex(v)

        # New "upper" simplex
        S_new_u = Simplex(gen, S.hg_n, S.p_hgr_h, S.generation_cycle, self.dim)
        S_new_u.add_vertex(
            S()[S_new_u.generation_cycle + 1])  # First vertex on new long edge

        for v in S()[1:-1]:  # Remaining vertices
            S_new_u.add_vertex(v)

        for k, v in enumerate(S()[1:-1]):  # iterate through inner vertices
            # for easier k / gci tracking
            k += 1
            # if k == 0:
            #    continue  # We do this rather than S[1:-1]
            # for easier k / gci tracking
            if k == (S.generation_cycle + 1):
                S_new_u.add_vertex(V_new)
            else:
                S_new_u.add_vertex(v)

        S_new_u.add_vertex(S()[-1])  # Second vertex on new long edge

        # for i, v in enumerate(S_new_u()):
        #    print(f'S_new_u()[{i}].x = {v.x}')

        self.H[gen].append(S_new_l)
        if 1:
            self.H[gen].append(S_new_u)

        return

    @lru_cache(maxsize=None)
    def generate_sub_cell_2(self, origin, suprenum, v_x_t):  # No hits
        """
        Use the origin and suprenum vectors to find a new cell in that
        subspace direction

        NOTE: NOT CURRENTLY IN USE!

        Parameters
        ----------
        origin : tuple vector (hashable)
        suprenum : tuple vector (hashable)

        Returns
        -------

        """
        t1 = self.generate_sub_cell_t1(origin, v_x_t)
        t2 = self.generate_sub_cell_t2(suprenum, v_x_t)
        vec = t1 + t2
        return tuple(vec)

    @lru_cache(maxsize=None)
    def generate_sub_cell_t1(self, origin, v_x):
        # TODO: Calc these arrays outside
        v_o = numpy.array(origin)
        return v_o - v_o * numpy.array(v_x)

    @lru_cache(maxsize=None)
    def generate_sub_cell_t2(self, suprenum, v_x):
        v_s = numpy.array(suprenum)
        return v_s * numpy.array(v_x)

    # Plots
    def plot_complex(self):
        """
             Here C is the LIST of simplexes S in the
             2 or 3 dimensional complex

             To plot a single simplex S in a set C, use ex. [C[0]]
        """
        from matplotlib import pyplot
        if self.dim == 2:
            pyplot.figure()
            for C in self.H:
                for c in C:
                    for v in c():
                        if self.bounds is None:
                            x_a = numpy.array(v.x, dtype=float)
                        else:
                            x_a = numpy.array(v.x, dtype=float)
                            for i in range(len(self.bounds)):
                                x_a[i] = (x_a[i] * (self.bounds[i][1]
                                                    - self.bounds[i][0])
                                          + self.bounds[i][0])

                        # logging.info('v.x_a = {}'.format(x_a))

                        pyplot.plot([x_a[0]], [x_a[1]], 'o')

                        xlines = []
                        ylines = []
                        for vn in v.nn:
                            if self.bounds is None:
                                xn_a = numpy.array(vn.x, dtype=float)
                            else:
                                xn_a = numpy.array(vn.x, dtype=float)
                                for i in range(len(self.bounds)):
                                    xn_a[i] = (xn_a[i] * (self.bounds[i][1]
                                                          - self.bounds[i][0])
                                               + self.bounds[i][0])

                            # logging.info('vn.x = {}'.format(vn.x))

                            xlines.append(xn_a[0])
                            ylines.append(xn_a[1])
                            xlines.append(x_a[0])
                            ylines.append(x_a[1])

                        pyplot.plot(xlines, ylines)

            if self.bounds is None:
                pyplot.ylim([-1e-2, 1 + 1e-2])
                pyplot.xlim([-1e-2, 1 + 1e-2])
            else:
                pyplot.ylim(
                    [self.bounds[1][0] - 1e-2, self.bounds[1][1] + 1e-2])
                pyplot.xlim(
                    [self.bounds[0][0] - 1e-2, self.bounds[0][1] + 1e-2])

            pyplot.show()

        elif self.dim == 3:
            from mpl_toolkits.mplot3d import Axes3D
            fig = pyplot.figure()
            ax = fig.add_subplot(111, projection='3d')

            for C in self.H:
                for c in C:
                    for v in c():
                        x = []
                        y = []
                        z = []
                        # logging.info('v.x = {}'.format(v.x))
                        x.append(v.x[0])
                        y.append(v.x[1])
                        z.append(v.x[2])
                        for vn in v.nn:
                            x.append(vn.x[0])
                            y.append(vn.x[1])
                            z.append(vn.x[2])
                            x.append(v.x[0])
                            y.append(v.x[1])
                            z.append(v.x[2])
                            # logging.info('vn.x = {}'.format(vn.x))

                        ax.plot(x, y, z, label='simplex')

            pyplot.show()
        else:
            print("dimension higher than 3 or wrong complex format")
        return


class Cell:
    """
    Contains a cell that is symmetric to the initial hypercube triangulation
    """

    def __init__(self, p_gen, p_hgr, p_hgr_h, origin, suprenum):
        self.p_gen = p_gen  # parent generation
        self.p_hgr = p_hgr  # parent homology group rank
        self.p_hgr_h = p_hgr_h  #
        self.hg_n = None
        self.hg_d = None

        # Maybe add parent homology group rank total history
        # This is the sum off all previously split cells
        # cumulatively throughout its entire history
        self.C = []
        self.origin = origin
        self.suprenum = suprenum
        self.centroid = None  # (Not always used)
        # TODO: self.bounds

    def __call__(self):
        return self.C

    def add_vertex(self, V):
        if V not in self.C:
            self.C.append(V)

    def homology_group_rank(self):
        """
        Returns the homology group order of the current cell
        """
        if self.hg_n is not None:
            return self.hg_n
        else:
            hg_n = 0
            for v in self.C:
                if v.minimiser():
                    hg_n += 1

            self.hg_n = hg_n
            return hg_n

    def homology_group_differential(self):
        """
        Returns the difference between the current homology group of the
        cell and it's parent group
        """
        if self.hg_d is not None:
            return self.hg_d
        else:
            self.hgd = self.hg_n - self.p_hgr
            return self.hgd

    def polytopial_sperner_lemma(self):
        """
        Returns the number of stationary points theoretically contained in the
        cell based information currently known about the cell
        """
        pass

    def print_out(self):
        """
        Print the current cell to console
        """
        for v in self():
            print("Vertex: {}".format(v.x))
            constr = 'Connections: '
            for vc in v.nn:
                constr += '{} '.format(vc.x)

            print(constr)
            print('Order = {}'.format(v.order))


class Simplex:
    """
    Contains a simplex that is symmetric to the initial symmetry constrained
    hypersimplex triangulation
    """

    def __init__(self, p_gen, p_hgr, p_hgr_h, generation_cycle, dim):
        self.p_gen = p_gen  # parent generation
        self.p_hgr = p_hgr  # parent homology group rank
        self.p_hgr_h = p_hgr_h  #
        self.hg_n = None
        self.hg_d = None

        gci_n = (generation_cycle + 1) % (dim - 1)
        gci = gci_n
        self.generation_cycle = gci

        # Maybe add parent homology group rank total history
        # This is the sum off all previously split cells
        # cumulatively throughout its entire history
        self.C = []

    def __call__(self):
        return self.C

    def add_vertex(self, V):
        if V not in self.C:
            self.C.append(V)

    def homology_group_rank(self):
        """
        Returns the homology group order of the current cell
        """
        if self.hg_n is not None:
            return self.hg_n
        else:
            hg_n = 0
            for v in self.C:
                if v.minimiser():
                    hg_n += 1

            self.hg_n = hg_n
            return hg_n

    def homology_group_differential(self):
        """
        Returns the difference between the current homology group of the
        cell and it's parent group
        """
        if self.hg_d is not None:
            return self.hg_d
        else:
            self.hgd = self.hg_n - self.p_hgr
            return self.hgd

    def polytopial_sperner_lemma(self):
        """
        Returns the number of stationary points theoretically contained in the
        cell based information currently known about the cell
        """
        pass

    def print_out(self):
        """
        Print the current cell to console
        """
        for v in self():
            print("Vertex: {}".format(v.x))
            constr = 'Connections: '
            for vc in v.nn:
                constr += '{} '.format(vc.x)

            print(constr)
            print('Order = {}'.format(v.order))


class Vertex:
    def __init__(self, x, bounds=None, func=None, func_args=(), g_cons=None,
                 g_cons_args=(), nn=None, Ind=None):
        import numpy
        self.x = x
        self.order = sum(x)
        if bounds is None:
            x_a = numpy.array(x, dtype=float)
        else:
            x_a = numpy.array(x, dtype=float)
            for i in range(len(bounds)):
                x_a[i] = (x_a[i] * (bounds[i][1] - bounds[i][0])
                          + bounds[i][0])

                # print(f'x = {x}; x_a = {x_a}')
        # TODO: Make saving the array structure optional
        self.x_a = x_a

        # Note Vertex is only initiate once for all x so only
        # evaluated once
        if func is not None:
            if g_cons is not None:
                self.feasible = True
                for ind, g in enumerate(g_cons):
                    if g(self.x_a, *g_cons_args[ind]) < 0.0:
                        self.f = numpy.inf
                        self.feasible = False
                if self.feasible:
                    self.f = func(x_a, *func_args)

            else:
                self.f = func(x_a, *func_args)

        if nn is not None:
            self.nn = nn
        else:
            self.nn = set()

        self.fval = None
        self.check_min = True

        # Index:
        if Ind is not None:
            self.Ind = Ind

    def __hash__(self):
        # return hash(tuple(self.x))
        return hash(self.x)

    def connect(self, v):
        if v is not self and v not in self.nn:
            self.nn.add(v)
            v.nn.add(self)

            # self.min = self.minimiser()
            if self.minimiser():
                # if self.f > v.f:
                #    self.min = False
                # else:
                v.min = False
                v.check_min = False

            # TEMPORARY
            self.check_min = True
            v.check_min = True

    def disconnect(self, v):
        if v in self.nn:
            self.nn.remove(v)
            v.nn.remove(self)
            self.check_min = True
            v.check_min = True

    def minimiser(self):
        # NOTE: This works pretty well, never call self.min,
        #       call this function instead
        if self.check_min:
            # Check if the current vertex is a minimiser
            # self.min = all(self.f <= v.f for v in self.nn)
            self.min = True
            for v in self.nn:
                # if self.f <= v.f:
                # if self.f > v.f: #TODO: LAST STABLE
                if self.f >= v.f:  # TODO: AttributeError: 'Vertex' object has no attribute 'f'
                    # if self.f >= v.f:
                    self.min = False
                    break

            self.check_min = False

        return self.min


class VertexCache:
    def __init__(self, func, func_args=(), bounds=None, g_cons=None,
                 g_cons_args=(), indexed=True):

        self.cache = {}
        # self.cache = set()
        self.func = func
        self.g_cons = g_cons
        self.g_cons_args = g_cons_args
        self.func_args = func_args
        self.bounds = bounds
        self.nfev = 0
        self.size = 0

        if indexed:
            self.Index = -1

    def __getitem__(self, x, indexed=True):
        try:
            return self.cache[x]
        except KeyError:
            if indexed:
                self.Index += 1
                xval = Vertex(x, bounds=self.bounds,
                              func=self.func, func_args=self.func_args,
                              g_cons=self.g_cons,
                              g_cons_args=self.g_cons_args,
                              Ind=self.Index)
            else:
                xval = Vertex(x, bounds=self.bounds,
                              func=self.func, func_args=self.func_args,
                              g_cons=self.g_cons,
                              g_cons_args=self.g_cons_args)

            # logging.info("New generated vertex at x = {}".format(x))
            # NOTE: Surprisingly high performance increase if logging is commented out
            self.cache[x] = xval

            # TODO: Check
            if self.func is not None:
                if self.g_cons is not None:
                    # print(f'xval.feasible = {xval.feasible}')
                    if xval.feasible:
                        self.nfev += 1
                        self.size += 1
                    else:
                        self.size += 1
                else:
                    self.nfev += 1
                    self.size += 1

            return self.cache[x]
