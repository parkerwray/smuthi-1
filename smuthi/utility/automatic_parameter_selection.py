"""Functions that assist the user in the choice of suitable numerical simulation parameters."""

import sys
import numpy as np
import smuthi.fields as flds
import smuthi.postprocessing.far_field as ff
from smuthi.fields import angular_frequency
import smuthi.utility.logging as log


def evaluate(simulation, detector):
    """Run a simulation and evaluate the detector.
    Args:
        simulation (smuthi.simulation.Simulation):    simulation object
        detector (method or str):                     Specify a method that accepts a simulation as input and returns
                                                      a float. Otherwise, type "extinction cross section" to use the
                                                      extinction cross section as a detector.

    Returns:
        The detector value (float)
    """
    if detector == "extinction cross section":
        def detector(sim):
            ecs = ff.extinction_cross_section(initial_field=sim.initial_field,
                                              particle_list=sim.particle_list,
                                              layer_system=sim.layer_system)
            return ecs["top"] + ecs["bottom"]

    with log.LoggerMuted():
        simulation.run()
        return detector(simulation)


def converge_l_max(particle,
                   simulation,
                   detector="extinction cross section",
                   tolerance=1e-3,
                   max_iter=100,
                   current_value=None):
    """Find suitable multipole cutoff degree `l_max` for a given particle and simulation. The routine starts with the
    current `l_max` of the particle. The value of `l_max` is successively incremented in a loop until the resulting
    relative change in the detector value is smaller than the specified tolerance. The method updates the input
    particle object with the `l_max` value for which convergence has been achieved.

    Args:
        particle (smuthi.particles.Particle):         Particle for which the l_max is incremented
        simulation (smuthi.simulation.Simulation):    Simulation object containing the particle
        detector (function or string):                Function that accepts a simulation object and returns a detector
                                                      value the change of which is used to define convergence.
                                                      Alternatively, use "extinction cross section" (default) to have
                                                      the extinction cross section as the detector value.
        tolerance (float):                            Relative tolerance for the detector value change.
        max_iter (int):                               Break convergence loop after that number of iterations, even if
                                                      no convergence has been achieved.
        current_value (float):                        Start value of detector (for current settings). If not
                                                      specified the method starts with a simulation for the current
                                                      settings.

    Returns:
        Detector value of converged or break-off parameter settings.
      """
    print("")
    print("------------------------")
    log.write_blue("Searching suitable l_max")
    print("Start value: l_max=%i" % particle.l_max)

    if current_value is None:
        current_value = evaluate(simulation, detector)

    for _ in range(max_iter):
        old_l_max = particle.l_max
        particle.l_max = old_l_max + 1  # l_max increment
        particle.m_max = particle.l_max

        print("---------------------------------------")
        print("Try l_max = %i and m_max=%i" % (particle.l_max, particle.m_max))

        new_value = evaluate(simulation, detector)
        rel_diff = abs(new_value - current_value) / abs(current_value)
        print("Old detector value:", current_value)
        print("New detector value:", new_value)
        print("Relative difference:", rel_diff)

        if rel_diff < tolerance:  # in this case: discard l_max increment
            particle.l_max = old_l_max
            particle.m_max = old_l_max
            log.write_green("Relative difference smaller than tolerance. Keep l_max = %i" % particle.l_max)
            return current_value
        else:
            current_value = new_value

    log.write_red("No convergence achieved. Keep l_max = %i"%particle.l_max)
    return current_value


def converge_m_max(particle,
                   simulation,
                   detector="extinction cross section",
                   tolerance=1e-3,
                   current_value=None):
    """Find suitable multipole cutoff order `m_max` for a given particle and simulation. The routine starts with the
    current `l_max` of the particle, i.e. with `m_max=l_max`. The value of `m_max` is successively decremented in a loop
    until the resulting relative change in the detector value is larger than the specified tolerance. The method updates
    the input particle object with the so determined `m_max`.

    Args:
        particle (smuthi.particles.Particle):         Particle for which suitable m_max is searched
        simulation (smuthi.simulation.Simulation):    Simulation object containing the particle
        detector (function or string):                Function that accepts a simulation object and returns a detector
                                                      value the change of which is used to define convergence.
                                                      Alternatively, use "extinction cross section" (default) to have
                                                      the extinction cross section as the detector value.
        tolerance (float):                            Relative tolerance for the detector value change.
        max_iter (int):                               Break convergence loop after that number of iterations, even if
                                                      no convergence has been achieved.
        current_value (float):                        Start value of detector (for current settings). If not
                                                      specified the method starts with a simulation for the current
                                                      settings.

    Returns:
        Detector value of converged or break-off parameter settings.
    """
    print("")
    print("------------------------")
    log.write_blue("Searching suitable m_max")
    print("Start value: m_max=%i"%particle.m_max)

    if current_value is None:
        current_value = evaluate(simulation, detector)

    for m_max in range(particle.m_max, -1, -1):
        old_m_max = particle.m_max
        particle.m_max = m_max
        print("---------------------------------------")
        print("Try m_max=%i"%particle.m_max)
        new_value = evaluate(simulation, detector)
        rel_diff = abs(new_value - current_value) / abs(current_value)
        print("Old detector value:", current_value)
        print("New detector value:", new_value)
        print("Relative difference:", rel_diff)
        if rel_diff > tolerance:  # in this case: discard m_max decrement
            particle.m_max = old_m_max
            log.write_green("Relative difference larger than tolerance. Keep m_max = %i"%particle.m_max)
            return current_value
        else:
            current_value = new_value

    log.write_red("No convergence achieved. Keep m_max = %i" % particle.m_max)


def converge_multipole_cutoff(simulation,
                              detector="extinction cross section",
                              tolerance=1e-3,
                              max_iter=100,
                              current_value=None):
    """Find suitable multipole cutoff degree `l_max` and order `m_max` for all particles in a given simulation object.
    The method updates the input simulation object with the so determined multipole truncation values.

    Args:
        simulation (smuthi.simulation.Simulation):    Simulation object
        detector (function or string):                Function that accepts a simulation object and returns a detector
                                                      value the change of which is used to define convergence.
                                                      Alternatively, use "extinction cross section" (default) to have
                                                      the extinction cross section as the detector value.
        tolerance (float):                            Relative tolerance for the detector value change.
        max_iter (int):                               Break convergence loops after that number of iterations, even if
                                                      no convergence has been achieved.
        current_value (float):                        Start value of detector (for current settings). If not
                                                      specified the method starts with a simulation for the current
                                                      settings.

    Returns:
        Detector value of converged or break-off parameter settings.
    """
    print("")
    print("-----------------------------------")
    log.write_blue("Searching suitable multipole cutoff")

    for i, particle in enumerate(simulation.particle_list):
        print("")
        print("-------------------------------")
        log.write_blue("Checking particle number %i"%i)
        with log.LoggerIndented():
            current_value = converge_l_max(particle,
                                           simulation,
                                           detector,
                                           tolerance,
                                           max_iter,
                                           current_value)

            current_value = converge_m_max(particle,
                                           simulation,
                                           detector,
                                           tolerance,
                                           current_value)

    return current_value


def update_contour(simulation, neff_imag=5e-3, neff_max=None, neff_max_offset=0.5, neff_step=2e-3):
    """Update the default `k_parallel` arrays in smuthi.fields with a newly constructed Sommerfeld integral
    contours.

    Args:
        simulation (smuthi.simulation.Simulation):      Simulation object
        neff_imag (float):                              Extent of the contour into the negative imaginary direction
                                                        (in terms of effective refractive index, n_eff=kappa/omega).
        neff_max (float):                               Truncation value of contour (in terms of effective refractive
                                                        index).
        neff_max_offset (float):                        If no value for `neff_max` is specified, use the last estimated
                                                        singularity location plus this value (in terms of effective
                                                        refractive index).
        neff_step (float):                              Discretization of the contour (in terms of eff. refractive
                                                        index).
        update_default_contours (logical)               If true, overwrite the default contours in smuthi.fields module.
                                                        Otherwise, overwrite simulation.k_parallel array
    """
    simulation.neff_imag = neff_imag
    simulation.neff_max = neff_max
    simulation.neff_max_offset = neff_max_offset
    simulation.neff_resolution = neff_step
    simulation.set_default_initial_field_contour()
    simulation.set_default_Sommerfeld_contour()

    simulation.k_parallel = flds.default_Sommerfeld_k_parallel_array


def converge_neff_max(simulation,
                      detector="extinction cross section",
                      tolerance=1e-3,
                      max_iter=20,
                      neff_imag=1e-2,
                      neff_step=2e-3,
                      neff_max_increment=0.5,
                      converge_lm=True):
    """Find a suitable truncation value for the multiple scattering Sommerfeld integral contour and update the
    simulation object accordingly.

    Args:
        simulation (smuthi.simulation.Simulation):    Simulation object
        detector (function or string):                Function that accepts a simulation object and returns a detector
                                                      value the change of which is used to define convergence.
                                                      Alternatively, use "extinction cross section" (default) to have
                                                      the extinction cross section as the detector value.
        tolerance (float):                            Relative tolerance for the detector value change.
        max_iter (int):                               Break convergence loops after that number of iterations, even if
                                                      no convergence has been achieved.
        neff_imag (float):                              Extent of the contour into the negative imaginary direction
                                                        (in terms of effective refractive index, n_eff=kappa/omega).
        neff_step (float):                              Discretization of the contour (in terms of eff. refractive
                                                        index).
        neff_max_increment (float):                     Increment the neff_max parameter with that step size
        converge_lm (logical):                          If set to true, update multipole truncation during each step
                                                        (this takes longer time, but is necessary for critical use cases
                                                        like flat particles on a substrate)

    Returns:
        Detector value for converged settings.
    """

    print("")
    print("---------------------------")
    log.write_blue("Searching suitable neff_max")

    update_contour(simulation=simulation, neff_imag=neff_imag, neff_max_offset=0, neff_step=neff_step)

    simulation.k_parallel = flds.reasonable_Sommerfeld_kpar_contour(
        vacuum_wavelength=simulation.initial_field.vacuum_wavelength,
        layer_refractive_indices=simulation.layer_system.refractive_indices,
        neff_imag=neff_imag,
        neff_max_offset=0,
        neff_resolution=neff_step)

    neff_max = simulation.k_parallel[-1] / angular_frequency(simulation.initial_field.vacuum_wavelength)
    print("Starting value: neff_max=%f"%neff_max.real)

    if converge_lm:
        with log.LoggerIndented():
            current_value = converge_multipole_cutoff(simulation=simulation,
                                                      detector=detector,
                                                      tolerance=tolerance/2,  # otherwise, results flucutate by tolerance and convergence check is compromised
                                                      max_iter=max_iter)
    else:
        current_value = evaluate(simulation, detector)

    for _ in range(max_iter):
        old_neff_max = neff_max
        neff_max = neff_max + neff_max_increment
        update_contour(simulation=simulation, neff_imag=neff_imag, neff_max=neff_max, neff_step=neff_step)

        print("---------------------------------------")
        print("Try neff_max = %f"%neff_max.real)

        if converge_lm:
            with log.LoggerIndented():
                new_value = converge_multipole_cutoff(simulation=simulation,
                                                      detector=detector,
                                                      tolerance=tolerance,
                                                      max_iter=max_iter,
                                                      current_value=current_value)
        else:
            new_value = evaluate(simulation, detector)

        rel_diff = abs(new_value - current_value) / abs(current_value)
        print("Old detector value:", current_value)
        print("New detector value:", new_value)
        print("Relative difference:", rel_diff)

        if rel_diff < tolerance:  # in this case: discard l_max increment
            neff_max = old_neff_max
            update_contour(simulation=simulation, neff_imag=neff_imag, neff_max=neff_max, neff_step=neff_step)
            log.write_green("Relative difference smaller than tolerance. Keep neff_max = %f"%neff_max.real)
            return current_value
        else:
            current_value = new_value

    log.write_red("No convergence achieved. Keep neff_max = %i"%neff_max)
    return None


def converge_neff_step(simulation,
                       detector="extinction cross section",
                       tolerance=1e-3,
                       max_iter=20,
                       neff_imag=1e-2,
                       neff_max=None,
                       neff_step=1e-2):
    """Find a suitable discretization step size for the multiple scattering Sommerfeld integral contour and update the
    simulation object accordingly.

    Args:
        simulation (smuthi.simulation.Simulation):    Simulation object
        detector (function or string):                Function that accepts a simulation object and returns a detector
                                                      value the change of which is used to define convergence.
                                                      Alternatively, use "extinction cross section" (default) to have
                                                      the extinction cross section as the detector value.
        tolerance (float):                            Relative tolerance for the detector value change.
        max_iter (int):                               Break convergence loops after that number of iterations, even if
                                                      no convergence has been achieved.
        neff_imag (float):                            Extent of the contour into the negative imaginary direction
                                                      (in terms of effective refractive index, n_eff=kappa/omega).
        neff_max (float):                             Truncation value of contour (in terms of effective refractive
                                                      index).
        neff_step (float):                            Discretization of the contour (in terms of eff. refractive
                                                      index) - start value for iteration

    Returns:
        Detector value for converged settings.
    """
    print("")
    print("-----------------------")
    log.write_blue("Find suitable neff_step")

    update_contour(simulation=simulation, neff_imag=neff_imag, neff_max=neff_max, neff_step=neff_step)
    print("Starting value: neff_step=%f" % neff_step)
    current_value = evaluate(simulation, detector)

    for _ in range(max_iter):
        old_neff_step = neff_step
        neff_step = neff_step / 2.0
        update_contour(simulation=simulation, neff_imag=neff_imag, neff_max=neff_max, neff_step=neff_step)

        print("---------------------------------------")
        print("Try neff_step = %f" % neff_step)

        new_value = evaluate(simulation, detector)

        rel_diff = abs(new_value - current_value) / abs(current_value)
        print("Old detector value:", current_value)
        print("New detector value:", new_value)
        print("Relative difference:", rel_diff)

        if rel_diff < tolerance:  # in this case: discard halfed neff_step
            neff_step = old_neff_step
            update_contour(simulation=simulation, neff_imag=neff_imag, neff_max=neff_max, neff_step=neff_step)
            log.write_green("Relative difference smaller than tolerance. Keep neff_step = %f" % neff_step)
            return current_value
        else:
            current_value = new_value

    log.write_red("No convergence achieved. Keep neff_step = %i" % neff_step)
    return None


def select_numerical_parameters(simulation,
                                detector="extinction cross section",
                                tolerance=1e-3,
                                max_iter=20,
                                neff_imag=1e-2,
                                neff_step=1e-2,
                                select_neff_max=True,
                                neff_max_increment=0.5,
                                neff_max=None,
                                select_neff_step=True,
                                select_multipole_cutoff=True,
                                relative_convergence=True,
                                suppress_simulation_output=True):
    """Trigger automatic selection routines for various numerical parameters.

    Args:
        simulation (smuthi.simulation.Simulation):    Simulation object from which parameters are read and into which
                                                      results are stored.
        detector (function or string):                Function that accepts a simulation object and returns a detector
                                                      value the change of which is used to define convergence.
                                                      Alternatively, use "extinction cross section" (default) to have
                                                      the extinction cross section as the detector value.
        tolerance (float):                            Relative tolerance for the detector value change.
        max_iter (int):                               Break convergence loops after that number of iterations, even if
                                                      no convergence has been achieved.
        neff_imag (float):                            Extent of the contour into the negative imaginary direction
                                                      (in terms of effective refractive index, n_eff=kappa/omega).
        neff_step (float):                            Discretization of the contour (in terms of eff. refractive
                                                      index) - if `select_neff_step` is true, this value will be
                                                      eventually overwritten. However, it is required in any case.
                                                      Default: 1e-2
        select_neff_max (logical):                    If set to true (default), the Sommerfeld integral truncation parameter
                                                      `neff_max` is determined automatically with the help of a
                                                      Cauchy convergence criterion.
        neff_max_increment (float):                   Only needed if `select_neff_max` is true.
                                                      Step size with which `neff_max` is incremented.
        neff_max (float):                             Only needed if `select_neff_max` is false.
                                                      Truncation value of contour (in terms of effective refractive
                                                      index).
        select_neff_step (logical):                   If set to true (default), the Sommerfeld integral discretization
                                                      parameter `neff_step` is determined automatically with the help of
                                                      a Cauchy convergence criterion.
        select_multipole_cutoff (logical):            If set to true (default), the multipole expansion cutoff
                                                      parameters `l_max` and `m_max` are determined automatically with
                                                      the help of a Cauchy convergence criterion.
        relative_convergence (logical):               If set to true (default), the `neff_max` convergence and the
                                                      `l_max` and `m_max` convergence routine are performed in the
                                                      spirit of relative convergence, i.e., the multipole expansion
                                                      convergence is checked again for each value of the Sommerfeld
                                                      integral truncation. This takes more time, but is required at
                                                      least in the case of flat particles near interfaces.
        suppress_simulation_output (logical):         If set to false (default), suppress any output from simulations
                                                      and only display convergence progress
    """
    print("")
    print("----------------------------------------")
    print("Starting automatic paramateter selection")
    print("----------------------------------------")

    if select_neff_max:
        converge_neff_max(simulation=simulation,
                          detector=detector,
                          tolerance=tolerance,
                          max_iter=max_iter,
                          neff_imag=neff_imag,
                          neff_step=neff_step,
                          neff_max_increment=neff_max_increment,
                          converge_lm=relative_convergence)
        neff_max = simulation.k_parallel[-1] / angular_frequency(simulation.initial_field.vacuum_wavelength)

    if select_multipole_cutoff:
        converge_multipole_cutoff(simulation=simulation,
                                  detector=detector,
                                  tolerance=tolerance,
                                  max_iter=max_iter)

    if select_neff_step:
        converge_neff_step(simulation=simulation,
                           detector=detector,
                           tolerance=tolerance,
                           max_iter=max_iter,
                           neff_imag=neff_imag,
                           neff_max=neff_max)
