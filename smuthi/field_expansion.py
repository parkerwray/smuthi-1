# -*- coding: utf-8 -*-
import numpy as np
import sympy.physics.wigner
import sympy
import smuthi.coordinates as coord
import smuthi.spherical_functions as sf


def multi_to_single_index(tau, l, m, l_max, m_max):
    r"""Unique single index for the totality of indices characterizing a svwf expansion coefficient.

    The mapping follows the scheme:

    +-------------+-------------+-------------+------------+
    |single index |    spherical wave expansion indices    |
    +=============+=============+=============+============+
    | :math:`n`   | :math:`\tau`| :math:`l`   | :math:`m`  |
    +-------------+-------------+-------------+------------+
    |     1       |     1       |      1      |   -1       |
    +-------------+-------------+-------------+------------+
    |     2       |     1       |      1      |    0       |
    +-------------+-------------+-------------+------------+
    |     3       |     1       |      1      |    1       |
    +-------------+-------------+-------------+------------+
    |     4       |     1       |      2      |   -2       |
    +-------------+-------------+-------------+------------+
    |     5       |     1       |      2      |   -1       |
    +-------------+-------------+-------------+------------+
    |     6       |     1       |      2      |    0       |
    +-------------+-------------+-------------+------------+
    |    ...      |    ...      |     ...     |   ...      |
    +-------------+-------------+-------------+------------+
    |    ...      |     1       |    l_max    |    m_max   |
    +-------------+-------------+-------------+------------+
    |    ...      |     2       |      1      |   -1       |
    +-------------+-------------+-------------+------------+
    |    ...      |    ...      |     ...     |   ...      |
    +-------------+-------------+-------------+------------+

    Args:
        tau (int):      Polarization index :math:`\tau`(0=spherical TE, 1=spherical TM)
        l (int):        Degree :math:`l` (1, ..., lmax)
        m (int):        Order :math:`m` (-min(l,mmax),...,min(l,mmax))
        l_max (int):    Maximal multipole degree
        m_max (int):    Maximal multipole order

    Returns:
        single index (int) subsuming :math:`(\tau, l, m)`
    """
    # use:
    # \sum_{l=1}^lmax (2\min(l,mmax)+1) = \sum_{l=1}^mmax (2l+1) + \sum_{l=mmax+1}^lmax (2mmax+1)
    #                                   = 2*(1/2*mmax*(mmax+1))+mmax  +  (lmax-mmax)*(2*mmax+1)
    #                                   = mmax*(mmax+2)               +  (lmax-mmax)*(2*mmax+1)
    tau_blocksize = m_max * (m_max + 2) + (l_max - m_max) * (2 * m_max + 1)
    n = tau * tau_blocksize
    if (l - 1) <= m_max:
        n += (l - 1) * (l - 1 + 2)
    else:
        n += m_max * (m_max + 2) + (l - 1 - m_max) * (2 * m_max + 1)
    n += m + min(l, m_max)
    return n


def blocksize(l_max, m_max):
    """Number of coefficients in outgoing or regular spherical wave expansion for a single particle.

    Args:
        l_max (int):    Maximal multipole degree
        m_max (int):    Maximal multipole order
    Returns:
         Number of indices for one particle, which is the maximal index plus 1."""
    return multi_to_single_index(tau=1, l=l_max, m=m_max, l_max=l_max, m_max=m_max) + 1


class SphericalWaveExpansion:
    def __init__(self, k, l_max, m_max=None, type=None, reference_point=None, valid_between=None):
        self.k = k
        self.l_max = l_max
        if m_max:
            self.m_max = m_max
        else:
            self.m_max = l_max
        self.coefficients = np.zeros(blocksize(self.l_max, self.m_max), dtype=complex)
        self.type = type  # 'regular' or 'outgoing'
        self.reference_point = reference_point
        self.valid_between = valid_between

    def coefficients_tlm(self, tau, l, m):
        n = multi_to_single_index(tau, l, m, self.l_max, self.m_max)
        return self.coefficients[n]

    def electric_field(self, x, y, z):
        xr = x - self.reference_point[0]
        yr = y - self.reference_point[1]
        zr = z - self.reference_point[2]
        ex = np.zeros(len(x), dtype=complex)
        ey = np.zeros(len(x), dtype=complex)
        ez = np.zeros(len(x), dtype=complex)
        for tau in range(2):
            for m in range(-self.m_max, self.m_max + 1):
                for l in range(max(1, abs(m)), self.l_max + 1):
                    b = self.coefficients_tlm(tau, l, m)
                    if self.type == 'regular':
                        Nx, Ny, Nz = spherical_vector_wave_function(xr, yr, zr, self.k, 1, tau, l, m)
                    elif self.type == 'outgoing':
                        Nx, Ny, Nz = spherical_vector_wave_function(xr, yr, zr, self.k, 3, tau, l, m)
                    ex += b * Nx
                    ey += b * Ny
                    ez += b * Nz
        return ex, ey, ez

    def __add__(self, other):
        if not (self.k == other.k and self.l_max == other.l_max and self.m_max == other.m_max
                and self.type == other.type and self.reference_point == other.reference_point):
            raise ValueError('SphericalWaveExpansions are inconsistent.')
        swe_sum = SphericalWaveExpansion(k=self.k, l_max=self.l_max, m_max=self.m_max, type=self.type,
                                         reference_point=self.reference_point)
        if self.valid_between:
            swe_sum.valid_between = (max(min(self.valid_between), min(other.valid_between)),
                                     min(max(self.valid_between), max(other.valid_between)))
        else:
            swe_sum.valid_between = None
        swe_sum.coefficients = self.coefficients + other.coefficients
        return swe_sum


class PlaneWaveExpansion:
    r"""A class to manage plane wave expansions of the form

    .. math::
        \mathbf{E}(\mathbf{r}) = \sum_{j=1}^2 \iint \mathrm{d}^2\mathbf{k}_\parallel \, g_{j}(\kappa, \alpha)
        \mathbf{\Phi}^\pm_j(\kappa, \alpha; \mathbf{r} - \mathbf{r}_i)

    for :math:`\mathbf{r}` located in a layer defined by :math:`z\in [z_{min}, z_{max}]`
    and :math:`\mathrm{d}^2\mathbf{k}_\parallel = \kappa\,\mathrm{d}\alpha\,\mathrm{d}\kappa` and the double integral
    runs over :math:`\alpha\in[0, 2\pi]` and :math:`\kappa\in[0,\kappa_\mathrm{max}]`. Further,
    :math:`\mathbf{\Phi}^\pm_j` are the PVWFs, see :meth:`plane_vector_wave_function`.

    Internally, the expansion coefficients :math:`g_{ij}^\pm(\kappa, \alpha)` are stored as a list of 4-dimensional
    arrays.
    If the attributes k_parallel and azimuthal_angles have only a single entry, a discrete distribution is
    assumed:

    .. math::
        g_{ij}^-(\kappa, \alpha) \sim \delta^2(\mathbf{k}_\parallel - \mathbf{k}_{\parallel, 0})

    .. todo: update attributes doc

    Args:
        n_effective (ndarray):                      :math:`n_\mathrm{eff} = \kappa / \omega`, can be float or complex
                                                    numpy.array
        azimuthal_angles (ndarray):                 :math:`\alpha`, from 0 to :math:`2\pi`
        layer_system (smuthi.layers.LayerSystem):   Layer system in which the field is expanded

    Attributes:
        k_parallel (array): Array of in-plane wavenumbers
        azimuthal_angles (array): Azimuthal propagation angles of partial plane waves
        layer_system (smuthi.layers.LayerSystem): Layer system object to which the plane wave expansion refers.
        coefficients (list of numpy arrays): coefficients[i][j, pm, k, l] contains
            :math:`g^\pm_{ij}(\kappa_{k}, \alpha_{l})`, where :math:`\pm` is + for pm = 0 and :math:`\pm` is - for
            pm = 1, and the coordinates :math:`\kappa_{k}` and :math:`\alpha_{l}` correspond to n_effective[k] times the
            angular frequency and azimuthal_angles[l], respectively.
    """
    def __init__(self, k, k_parallel=None, azimuthal_angles=None, type=None, reference_point=None, valid_between=None):

        self.k = k
        if hasattr(k_parallel, '__len__'):
            self.k_parallel = np.array(k_parallel)
        else:
            self.k_parallel = np.array([k_parallel])
        if hasattr(azimuthal_angles, '__len__'):
            self.azimuthal_angles = np.array(azimuthal_angles)
        else:
            self.azimuthal_angles = np.array([azimuthal_angles])
        self.type = type  # 'upgoing' or 'downgoing'
        self.reference_point = reference_point
        self.valid_between = valid_between

        # The coefficients :math:`g^\pm_{j}(\kappa,\alpha) are represented as a 3-dimensional numpy.ndarray.
        # The indices are:
        # -  polarization (0=TE, 1=TM)
        # - index of the kappa dimension
        # - index of the alpha dimension
        self.coefficients = np.zeros((2, len(self.k_parallel), len(self.azimuthal_angles)), dtype=complex)

    def k_parallel_grid(self):
        """Meshgrid of n_effective with respect to azimuthal_angles"""
        kp_grid, _ = np.meshgrid(self.k_parallel, self.azimuthal_angles, indexing='ij')
        return kp_grid

    def azimuthal_angle_grid(self):
        """Meshgrid of azimuthal_angles with respect to n_effective"""
        _, a_grid = np.meshgrid(self.k_parallel, self.azimuthal_angles, indexing='ij')
        return a_grid

    def k_z(self):
        if self.type == 'upgoing':
            kz = coord.k_z(k_parallel=self.k_parallel, k=self.k)
        elif self.type == 'downgoing':
            kz = -coord.k_z(k_parallel=self.k_parallel, k=self.k)
        else:
            raise ValueError('pwe type undefined')
        return kz

    def k_z_grid(self):
        if self.type == 'upgoing':
            kz = coord.k_z(k_parallel=self.k_parallel_grid(), k=self.k)
        elif self.type == 'downgoing':
            kz = -coord.k_z(k_parallel=self.k_parallel_grid(), k=self.k)
        else:
            raise ValueError('pwe type undefined')
        return kz

    def __add__(self, other):
        if not (self.k == other.k and all(self.k_parallel == other.k_parallel)
                and all(self.azimuthal_angles == other.azimuthal_angles) and self.type == other.type
                and self.reference_point == other.reference_point):
            raise ValueError('Plane wave expansion are inconsistent.')
        pwe_sum = PlaneWaveExpansion(k=self.k, k_parallel=self.k_parallel, azimuthal_angles=self.azimuthal_angles,
                                     type=self.type, reference_point=self.reference_point)
        pwe_sum.valid_between = (max(min(self.valid_between), min(other.valid_between)),
                                 min(max(self.valid_between), max(other.valid_between)))
        pwe_sum.coefficients = self.coefficients + other.coefficients
        return pwe_sum

    def electric_field(self, x, y, z):
        """To do: doc, check if z inside domain of validity"""
        xr = x - self.reference_point[0]
        yr = y - self.reference_point[1]
        zr = z - self.reference_point[2]

        kpgrid = self.k_parallel_grid()
        agrid = self.azimuthal_angle_grid()
        kx = kpgrid * np.cos(agrid)
        ky = kpgrid * np.sin(agrid)
        kz = self.k_z_grid()

        kr = np.zeros((len(x), len(self.k_parallel), len(self.azimuthal_angles)), dtype=complex)
        kr += np.tensordot(xr, kx, axes=0)
        kr += np.tensordot(yr, ky, axes=0)
        kr += np.tensordot(zr, kz, axes=0)
        eikr = np.exp(1j * kr)

        integrand_x = np.zeros((len(x), len(self.k_parallel), len(self.azimuthal_angles)), dtype=complex)
        integrand_y = np.zeros((len(x), len(self.k_parallel), len(self.azimuthal_angles)), dtype=complex)
        integrand_z = np.zeros((len(x), len(self.k_parallel), len(self.azimuthal_angles)), dtype=complex)

        # pol=0
        integrand_x += (-np.sin(agrid) * self.coefficients[0, :, :])[None, :, :] * eikr
        integrand_y += (np.cos(agrid) * self.coefficients[0, :, :])[None, :, :] * eikr

        # pol=1
        integrand_x += (np.cos(agrid) * kz / self.k * self.coefficients[1, :, :])[None, :, :] * eikr
        integrand_y += (np.sin(agrid) * kz / self.k * self.coefficients[1, :, :])[None, :, :] * eikr
        integrand_z += (-kpgrid / self.k * self.coefficients[1, :, :])[None, :, :] * eikr

        if len(self.k_parallel) > 1:
            ex = np.trapz(np.trapz(integrand_x, self.azimuthal_angles) * self.k_parallel, self.k_parallel)
            ey = np.trapz(np.trapz(integrand_y, self.azimuthal_angles) * self.k_parallel, self.k_parallel)
            ez = np.trapz(np.trapz(integrand_z, self.azimuthal_angles) * self.k_parallel, self.k_parallel)
        else:
            ex = np.squeeze(integrand_x)
            ey = np.squeeze(integrand_y)
            ez = np.squeeze(integrand_z)

        return ex, ey, ez


def pwe_to_swe_conversion(pwe, l_max, m_max, reference_point):

    if reference_point[2] < min(pwe.valid_between) or reference_point[2] > max(pwe.valid_between):
        raise ValueError('reference point not inside domain of pwe validity')

    swe = SphericalWaveExpansion(k=pwe.k, l_max=l_max, m_max=m_max, type='regular', reference_point=reference_point)
    kpgrid = pwe.k_parallel_grid()
    agrid = pwe.azimuthal_angle_grid()
    kx = kpgrid * np.cos(agrid)
    ky = kpgrid * np.sin(agrid)
    kz = pwe.k_z_grid()
    kzvec = pwe.k_z()

    kvec = np.array([kx, ky, kz])
    rswe_mn_rpwe = np.array(reference_point) - np.array(pwe.reference_point)

    # phase factor for the translation of the reference point from rvec_iS to rvec_S
    ejkriSS = np.exp(1j * np.tensordot(kvec, rswe_mn_rpwe, axes=([0], [0])))

    # phase factor times pwe coefficients
    gejkriSS = pwe.coefficients * ejkriSS[None, :, :]  # indices: pol, jk, ja

    for tau in range(2):
        for m in range(-m_max, m_max + 1):
            emjma = np.exp(-1j * m * pwe.azimuthal_angles)
            for l in range(max(1, abs(m)), l_max + 1):
                ak_integrand = np.zeros(kpgrid.shape, dtype=complex)
                for pol in range(2):
                    Bdag = transformation_coefficients_VWF(tau, l, m, pol=pol, kp=pwe.k_parallel, kz=kzvec, dagger=True)
                    ak_integrand += (np.outer(Bdag, emjma) * gejkriSS[pol, :, :])
                if len(pwe.k_parallel) > 1:
                    an = np.trapz(np.trapz(ak_integrand, pwe.azimuthal_angles) * pwe.k_parallel, pwe.k_parallel) * 4
                else:
                    an = ak_integrand * 4
                swe.coefficients[multi_to_single_index(tau, l, m, swe.l_max, swe.m_max)] = np.squeeze(an)
    return swe


def swe_to_pwe_conversion(swe, k_parallel, azimuthal_angles, reference_point, valid_between=(-np.inf, np.inf)):

    pwe_up = PlaneWaveExpansion(k=swe.k, k_parallel=k_parallel, azimuthal_angles=azimuthal_angles, type='upgoing',
                                reference_point=reference_point, valid_between=(swe.reference_point[2],
                                                                                max(valid_between)))

    pwe_down = PlaneWaveExpansion(k=swe.k, k_parallel=k_parallel, azimuthal_angles=azimuthal_angles, type='downgoing',
                                  reference_point=reference_point, valid_between=(min(valid_between),
                                                                                  swe.reference_point[2]))

    agrid = pwe_up.azimuthal_angle_grid()
    kpgrid = pwe_up.k_parallel_grid()

    kx = kpgrid * np.cos(agrid)
    ky = kpgrid * np.sin(agrid)
    kz_up = pwe_up.k_z_grid()
    kz_down = pwe_down.k_z_grid()

    kzvec = pwe_up.k_z()

    kvec_up = np.array([kx, ky, kz_up])
    kvec_down = np.array([kx, ky, kz_down])
    rpwe_mn_rswe = np.array(reference_point) - np.array(swe.reference_point)

    # phase factor for the translation of the reference point from rvec_S to rvec_iS
    ejkrSiS_up = np.exp(1j * np.tensordot(kvec_up, rpwe_mn_rswe, axes=([0], [0])))
    ejkrSiS_down = np.exp(1j * np.tensordot(kvec_down, rpwe_mn_rswe, axes=([0], [0])))

    for m in range(-swe.m_max, swe.m_max + 1):
        eima = np.exp(1j * m * pwe_up.azimuthal_angles)  # indices: alpha_idx
        for l in range(max(1, abs(m)), swe.l_max + 1):
            for tau in range(2):
                for pol in range(2):
                    b = swe.coefficients_tlm(tau, l, m)
                    B_up = transformation_coefficients_VWF(tau, l, m, pol, pwe_up.k_parallel, pwe_up.k_z())
                    pwe_up.coefficients[pol, :, :] += b * B_up[:, None] * eima[None, :]
                    B_down = transformation_coefficients_VWF(tau, l, m, pol, pwe_down.k_parallel, pwe_down.k_z())
                    pwe_down.coefficients[pol, :, :] += b * B_down[:, None] * eima[None, :]

    pwe_up.coefficients = pwe_up.coefficients / (2 * np.pi * kzvec[None, :, None] * swe.k) * ejkrSiS_up[None, :, :]
    pwe_down.coefficients = (pwe_down.coefficients / (2 * np.pi * kzvec[None, :, None] * swe.k)
                             * ejkrSiS_down[None, :, :])

    return pwe_up, pwe_down


def plane_vector_wave_function(x, y, z, kp, alpha, kz, pol):
    r"""Electric field components of plane wave (PVWF).

    .. math::
        \mathbf{\Phi}_j = \exp ( \mathrm{i} \mathbf{k} \cdot \mathbf{r} ) \hat{ \mathbf{e} }_j

    with :math:`\hat{\mathbf{e}}_0` denoting the unit vector in azimuthal direction ('TE' or 's' polarization),
    and :math:`\hat{\mathbf{e}}_1` denoting the unit vector in polar direction ('TM' or 'p' polarization).

    The input arrays should have one of the following dimensions:

        - x,y,z: (N x 1) matrix
        - kp,alpha,kz: (1 x M) matrix
        - Ex, Ey, Ez: (M x N) matrix

    or

        - x,y,z: (M x N) matrix
        - kp,alpha,kz: scalar
        - Ex, Ey, Ez: (M x N) matrix

    Args:
        x (numpy.ndarray): x-coordinate of position where to test the field (length unit)
        y (numpy.ndarray): y-coordinate of position where to test the field
        z (numpy.ndarray): z-coordinate of position where to test the field
        kp (numpy.ndarray): parallel component of k-vector (inverse length unit)
        alpha (numpy.ndarray): azimthal angle of k-vector (rad)
        kz (numpy.ndarray): z-component of k-vector (inverse length unit)
        pol (int): Polarization (0=TE, 1=TM)

    Returns:
        - x-coordinate of PVWF electric field (numpy.ndarray)
        - y-coordinate of PVWF electric field (numpy.ndarray)
        - z-coordinate of PVWF electric field (numpy.ndarray)
    """
    k = np.sqrt(kp**2 + kz**2)
    kx = kp * np.cos(alpha)
    ky = kp * np.sin(alpha)

    scalar_wave = np.exp(1j * (kx * x + ky * y + kz * z))

    if pol == 0:
        Ex = -np.sin(alpha) * scalar_wave
        Ey = np.cos(alpha) * scalar_wave
        Ez = scalar_wave - scalar_wave
    elif pol == 1:
        Ex = np.cos(alpha) * kz / k * scalar_wave
        Ey = np.sin(alpha) * kz / k * scalar_wave
        Ez = -kp / k * scalar_wave
    else:
        raise ValueError('Polarization must be 0 (TE) or 1 (TM)')

    return Ex, Ey, Ez


def spherical_vector_wave_function(x, y, z, k, nu, tau, l, m):
    """Electric field components of spherical vector wave function (SVWF). The conventions are chosen according to
    `A. Doicu, T. Wriedt, and Y. A. Eremin: "Light Scattering by Systems of Particles", Springer-Verlag, 2006
    <https://doi.org/10.1007/978-3-540-33697-6>`_

    Args:
        x (numpy.ndarray):      x-coordinate of position where to test the field (length unit)
        y (numpy.ndarray):      y-coordinate of position where to test the field
        z (numpy.ndarray):      z-coordinate of position where to test the field
        k (float or complex):   wavenumber (inverse length unit)
        nu (int):               1 for regular waves, 3 for outgoing waves
        tau (int):              spherical polarization, 0 for spherical TE and 1 for spherical TM
        l (int):                l=1,... multipole degree (polar quantum number)
        m (int):                m=-l,...,l multipole order (azimuthal quantum number)

    Returns:
        - x-coordinate of SVWF electric field (numpy.ndarray)
        - y-coordinate of SVWF electric field (numpy.ndarray)
        - z-coordinate of SVWF electric field (numpy.ndarray)
    """
    r = np.sqrt(x**2 + y**2 + z**2)
    theta = np.arccos(z / r)
    phi = np.arctan2(y, x)

    # unit vector in r-direction
    er_x = x / r
    er_y = y / r
    er_z = z / r

    # unit vector in theta-direction
    eth_x = np.cos(theta) * np.cos(phi)
    eth_y = np.cos(theta) * np.sin(phi)
    eth_z = -np.sin(theta)

    # unit vector in phi-direction
    eph_x = -np.sin(phi)
    eph_y = np.cos(phi)
    eph_z = x - x

    cos_thet = np.cos(theta)
    sin_thet = np.sin(theta)
    plm_list, pilm_list, taulm_list = sf.legendre_normalized(cos_thet, sin_thet, l)
    plm = plm_list[l][abs(m)]
    pilm = pilm_list[l][abs(m)]
    taulm = taulm_list[l][abs(m)]

    kr = k * r
    if nu == 1:
        bes = sf.spherical_bessel(l, kr)
        dxxz = sf.dx_xj(l, kr)
    elif nu == 3:
        bes = sf.spherical_hankel(l, kr)
        dxxz = sf.dx_xh(l, kr)
    else:
        raise ValueError('nu must be 1 (regular SVWF) or 3 (outgoing SVWF)')

    eimphi = np.exp(1j * m * phi)
    prefac = 1/np.sqrt(2 * l * (l + 1))
    if tau == 0:
        Ex = prefac * bes * (1j * m * pilm * eth_x - taulm * eph_x) * eimphi
        Ey = prefac * bes * (1j * m * pilm * eth_y - taulm * eph_y) * eimphi
        Ez = prefac * bes * (1j * m * pilm * eth_z - taulm * eph_z) * eimphi
    elif tau == 1:
        Ex = prefac * (l * (l + 1) * bes / kr * plm * er_x +
                       dxxz / kr * (taulm * eth_x + 1j * m * pilm * eph_x)) * eimphi
        Ey = prefac * (l * (l + 1) * bes / kr * plm * er_y +
                       dxxz / kr * (taulm * eth_y + 1j * m * pilm * eph_y)) * eimphi
        Ez = prefac * (l * (l + 1) * bes / kr * plm * er_z +
                       dxxz / kr * (taulm * eth_z + 1j * m * pilm * eph_z)) * eimphi
    else:
        raise ValueError('tau must be 0 (spherical TE) or 1 (spherical TM)')

    return Ex, Ey, Ez


def transformation_coefficients_VWF(tau, l, m, pol, kp=None, kz=None, pilm_list=None, taulm_list=None, dagger=False):
    r"""Transformation coefficients B to expand SVWF in PVWF and vice versa:

    .. math::
        B_{\tau l m,j}(x) = -\frac{1}{\mathrm{i}^{l+1}} \frac{1}{\sqrt{2l(l+1)}} (\mathrm{i} \delta_{j1} + \delta_{j2})
        (\delta_{\tau j} \tau_l^{|m|}(x) + (1-\delta_{\tau j} m \pi_l^{|m|}(x))

    For the definition of the :math:`\tau_l^m` and :math:`\pi_l^m` functions, see
    `A. Doicu, T. Wriedt, and Y. A. Eremin: "Light Scattering by Systems of Particles", Springer-Verlag, 2006
    <https://doi.org/10.1007/978-3-540-33697-6>`_

    Args:
        tau (int):          SVWF polarization, 0 for spherical TE, 1 for spherical TM
        l (int):            l=1,... SVWF multipole degree
        m (int):            m=-l,...,l SVWF multipole order
        pol (int):          PVWF polarization, 0 for TE, 1 for TM
        kp (numpy array):         PVWF in-plane wavenumbers
        kz (numpy array):         complex numpy-array: PVWF out-of-plane wavenumbers
        pilm_list (list):   2D list numpy-arrays: alternatively to kp and kz, pilm and taulm as generated with
                            legendre_normalized can directly be handed
        taulm_list (list):  2D list numpy-arrays: alternatively to kp and kz, pilm and taulm as generated with
                            legendre_normalized can directly be handed
        dagger (bool):      switch on when expanding PVWF in SVWF and off when expanding SVWF in PVWF

    Returns:
        Transformation coefficient as array (size like kp).
    """
    if pilm_list is None:
        k = np.sqrt(kp**2 + kz**2)
        ct = kz / k
        st = kp / k
        plm_list, pilm_list, taulm_list = sf.legendre_normalized(ct, st, l)

    if tau == pol:
        sphfun = taulm_list[l][abs(m)]
    else:
        sphfun = m * pilm_list[l][abs(m)]

    if dagger:
        if pol == 0:
            prefac = -1 / (-1j) ** (l + 1) / np.sqrt(2 * l * (l + 1)) * (-1j)
        elif pol == 1:
            prefac = -1 / (-1j) ** (l + 1) / np.sqrt(2 * l * (l + 1)) * 1
        else:
            raise ValueError('pol must be 0 (TE) or 1 (TM)')
    else:
        if pol == 0:
            prefac = -1 / (1j) ** (l + 1) / np.sqrt(2 * l * (l + 1)) * (1j)
        elif pol ==1:
            prefac = -1 / (1j) ** (l + 1) / np.sqrt(2 * l * (l + 1)) * 1
        else:
            raise ValueError('pol must be 0 (TE) or 1 (TM)')

    B = prefac * sphfun
    return B


def translation_coefficients_svwf(tau1, l1, m1, tau2, l2, m2, k, d, sph_hankel=None, legendre=None, exp_immphi=None):
    r"""Coefficients of the translation operator for the expansion of an outgoing spherical wave in terms of
    regular spherical waves with respect to a different origin:

    .. math::
        \mathbf{\Psi}_{\tau l m}^{(3)}(\mathbf{r} + \mathbf{d} = \sum_{\tau'} \sum_{l'} \sum_{m'}
        A_{\tau l m, \tau' l' m'} (\mathbf{d}) \mathbf{\Psi}_{\tau' l' m'}^{(1)}(\mathbf{r})

    for :math:`|\mathbf{r}|<|\mathbf{d}|`.

    Args:
        tau1 (int):             tau1=0,1: Original wave's spherical polarization
        l1 (int):               l=1,...: Original wave's SVWF multipole degree
        m1 (int):               m=-l,...,l: Original wave's SVWF multipole order
        tau2 (int):             tau2=0,1: Partial wave's spherical polarization
        l2 (int):               l=1,...: Partial wave's SVWF multipole degree
        m2 (int):               m=-l,...,l: Partial wave's SVWF multipole order
        k (float or complex):   wavenumber (inverse length unit)
        d (list):               translation vectors in format [dx, dy, dz] (length unit)
                                dx, dy, dz can be scalars or ndarrays
        sph_hankel (list):      Optional. sph_hankel[i] contains the spherical hankel funciton of degree i, evaluated at
                                k*d where d is the norm of the distance vector(s)
        legendre (list):        Optional. legendre[l][m] contains the legendre function of order l and degree m,
                                evaluated at cos(theta) where theta is the polar angle(s) of the distance vector(s)

    Returns:
        translation coefficient A (complex)

    """
    # spherical coordinates of d:
    dd = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)

    if exp_immphi is None:
        phid = np.arctan2(d[1], d[0])
        eimph = np.exp(1j * (m1 - m2) * phid)
    else:
        eimph = exp_immphi[m1][m2]

    if sph_hankel is None:
        sph_hankel = [sf.spherical_hankel(n, k * dd) for n in range(l1 + l2 + 1)]

    if legendre is None:
        costthetd = d[2] / dd
        sinthetd = np.sqrt(d[0] ** 2 + d[1] ** 2) / dd
        legendre, _, _ = sf.legendre_normalized(costthetd, sinthetd, l1 + l2)

    A = complex(0)
    for ld in range(abs(l1 - l2), l1 + l2 + 1):
        a5, b5 = ab5_coefficients(l1, m1, l2, m2, ld)
        if tau1 == tau2:
            A += a5 * sph_hankel[ld] * legendre[ld][abs(m1 - m2)]
        else:
            A += b5 * sph_hankel[ld] * legendre[ld][abs(m1 - m2)]
    A = eimph * A
    return A


def translation_coefficients_svwf_out_to_out(tau1, l1, m1, tau2, l2, m2, k, d, sph_bessel=None, legendre=None,
                                             exp_immphi=None):
    r"""Coefficients of the translation operator for the expansion of an outgoing spherical wave in terms of
    outgoing spherical waves with respect to a different origin:

    .. math::
        \mathbf{\Psi}_{\tau l m}^{(3)}(\mathbf{r} + \mathbf{d} = \sum_{\tau'} \sum_{l'} \sum_{m'}
        A_{\tau l m, \tau' l' m'} (\mathbf{d}) \mathbf{\Psi}_{\tau' l' m'}^{(3)}(\mathbf{r})

    for :math:`|\mathbf{r}|>|\mathbf{d}|`.

    Args:
        tau1 (int):             tau1=0,1: Original wave's spherical polarization
        l1 (int):               l=1,...: Original wave's SVWF multipole degree
        m1 (int):               m=-l,...,l: Original wave's SVWF multipole order
        tau2 (int):             tau2=0,1: Partial wave's spherical polarization
        l2 (int):               l=1,...: Partial wave's SVWF multipole degree
        m2 (int):               m=-l,...,l: Partial wave's SVWF multipole order
        k (float or complex):   wavenumber (inverse length unit)
        d (list):               translation vectors in format [dx, dy, dz] (length unit)
                                dx, dy, dz can be scalars or ndarrays
        sph_bessel (list):      Optional. sph_bessel[i] contains the spherical Bessel funciton of degree i, evaluated at
                                k*d where d is the norm of the distance vector(s)
        legendre (list):        Optional. legendre[l][m] contains the legendre function of order l and degree m,
                                evaluated at cos(theta) where theta is the polar angle(s) of the distance vector(s)

    Returns:
        translation coefficient A (complex)
    """
    # spherical coordinates of d:
    dd = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)

    if exp_immphi is None:
        phid = np.arctan2(d[1], d[0])
        eimph = np.exp(1j * (m1 - m2) * phid)
    else:
        eimph = exp_immphi[m1][m2]

    if sph_bessel is None:
        sph_bessel = [sf.spherical_bessel(n, k * dd) for n in range(l1 + l2 + 1)]

    if legendre is None:
        costthetd = d[2] / dd
        sinthetd = np.sqrt(d[0] ** 2 + d[1] ** 2) / dd
        legendre, _, _ = sf.legendre_normalized(costthetd, sinthetd, l1 + l2)

    A = complex(0), complex(0)
    for ld in range(abs(l1 - l2), l1 + l2 + 1):
        a5, b5 = ab5_coefficients(l1, m1, l2, m2, ld)
        if tau1==tau2:
            A += a5 * sph_bessel[ld] * legendre[ld][abs(m1 - m2)]
        else:
            A += b5 * sph_bessel[ld] * legendre[ld][abs(m1 - m2)]
    A = eimph * A
    return A


def ab5_coefficients(l1, m1, l2, m2, p, symbolic=False):
    """a5 and b5 are the coefficients used in the evaluation of the SVWF translation
    operator. Their computation is based on the sympy.physics.wigner package and is performed with symbolic numbers.

    Args:
        l1 (int):           l=1,...: Original wave's SVWF multipole degree
        m1 (int):           m=-l,...,l: Original wave's SVWF multipole order
        l2 (int):           l=1,...: Partial wave's SVWF multipole degree
        m2 (int):           m=-l,...,l: Partial wave's SVWF multipole order
        p (int):            p parameter
        symbolic (bool):    If True, symbolic numbers are returned. Otherwise, complex.

    Returns:
        A tuple (a5, b5) where a5 and b5 are symbolic or complex.
    """
    jfac = sympy.I ** (abs(m1 - m2) - abs(m1) - abs(m2) + l2 - l1 + p) * (-1) ** (m1 - m2)
    fac1 = sympy.sqrt((2 * l1 + 1) * (2 * l2 + 1) / sympy.S(2 * l1 * (l1 + 1) * l2 * (l2 + 1)))
    fac2a = (l1 * (l1 + 1) + l2 * (l2 + 1) - p * (p + 1)) * sympy.sqrt(2 * p + 1)
    fac2b = sympy.sqrt((l1 + l2 + 1 + p) * (l1 + l2 + 1 - p) * (p + l1 - l2) * (p - l1 + l2) * (2 * p + 1))
    wig1 = sympy.physics.wigner.wigner_3j(l1, l2, p, m1, -m2, -(m1 - m2))
    wig2a = sympy.physics.wigner.wigner_3j(l1, l2, p, 0, 0, 0)
    wig2b = sympy.physics.wigner.wigner_3j(l1, l2, p - 1, 0, 0, 0)

    if symbolic:
        a = jfac * fac1 * fac2a * wig1 * wig2a
        b = jfac * fac1 * fac2b * wig1 * wig2b
    else:
        a = complex(jfac * fac1 * fac2a * wig1 * wig2a)
        b = complex(jfac * fac1 * fac2b * wig1 * wig2b)
    return a, b
