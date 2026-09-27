"""Offline constrained surface-coordinate solver; not used by runtime.

The first fixture is a cylindrical open chart. Variables are angular binding
coordinates, not mesh positions or outer cage displacements. Axial coordinates
and normal offsets are held fixed. This is NOT a general mesh sliding solver.
"""
import numpy as np


def quadratic_active_set(hessian, reference, constraints, bounds, feasible, iterations=300):
    """Minimize .5*(x-reference)^T H (x-reference), subject to A*x>=b.

Requires an independently constructed feasible start. Primal active-set QP,
with feasible line search and nonnegative multipliers for active inequalities.
"""
    h, r = np.asarray(hessian,float), np.asarray(reference,float)
    a, b, x = np.asarray(constraints,float), np.asarray(bounds,float), np.array(feasible,float)
    if np.min(a@x-b)<-1e-9:
        raise ValueError('A feasible initial chart assignment is required')
    active=[]
    for iteration in range(iterations):
        gradient=h@(x-r)
        if active:
            aw=a[active]
            matrix=np.block([[h,-aw.T],[aw,np.zeros((len(active),len(active)))]])
            solution=np.linalg.lstsq(matrix,np.r_[-gradient,np.zeros(len(active))],rcond=None)[0]
            direction, multipliers=solution[:len(x)],solution[len(x):]
        else:
            direction=np.linalg.solve(h,-gradient);multipliers=np.empty(0)
        if np.linalg.norm(direction)<1e-10:
            if not active or multipliers.min()>=-1e-9:
                return x,dict(converged=True,iterations=iteration+1,
                    minimum_constraint_slack=float((a@x-b).min()),
                    energy=float(.5*(x-r)@h@(x-r)),active_constraints=len(active))
            active.pop(int(multipliers.argmin()));continue
        ad=a@direction;slack=a@x-b
        candidates=[i for i in range(len(b)) if i not in active and ad[i]<-1e-12]
        alpha=1.;blocking=None
        for i in candidates:
            ratio=max(0.,slack[i])/(-ad[i])
            if ratio<alpha:alpha=ratio;blocking=i
        x+=alpha*direction
        if blocking is not None:active.append(blocking)
        if (a@x-b).min()<-1e-8:raise ArithmeticError('Lost feasibility')
    return x,dict(converged=False,iterations=iterations,minimum_constraint_slack=float((a@x-b).min()))


def exterior_arc(radius, neighbor_distance, neighbor_radius, margin):
    """Allowed angular interval around +X obstacle, on a fixed-radius chart."""
    cosine=(radius**2+neighbor_distance**2-(neighbor_radius+margin)**2)/(2*radius*neighbor_distance)
    if cosine>=1:return 0.,2*np.pi
    if cosine<=-1:raise ValueError('No exposed points at this fixed radius')
    angle=float(np.arccos(cosine))
    return angle,2*np.pi-angle


def slide_open_arc(theta, radius, neighbor_distance, neighbor_radius, margin, strain_limit=.1):
    """Slide an ordered open strip within one exposed angular chart.

All axial rows share angular bindings by the fixture's translational symmetry.
Constrain angular edge changes to +/- strain_limit, penalize correspondence
displacement and differences of that displacement. No target answer is used.
"""
    theta=np.asarray(theta,float)
    steps=np.diff(theta)
    if np.any(steps<=0):raise ValueError('Expected an ordered, unwrapped open arc')
    low,high=exterior_arc(radius,neighbor_distance,neighbor_radius,margin)
    n=len(theta);difference=np.diff(np.eye(n),axis=0)
    a=np.vstack((np.eye(n),-np.eye(n),difference,-difference))
    b=np.r_[np.full(n,low),np.full(n,-high),(1-strain_limit)*steps,-(1+strain_limit)*steps]
    # Geometry-derived rigid angular translation is a feasible witness, not an
    # answer supplied by the benchmark. It preserves every garment edge.
    start=theta+max(0.,low-theta.min())
    if start.max()>high:raise ValueError('Rigid feasible initialization unavailable on this chart')
    h=np.eye(n)+difference.T@difference
    result,audit=quadratic_active_set(h,theta,a,b,start)
    audit.update(allowed_arc=[low,high],strain_limit=strain_limit,
                 binding_slide_max=float(np.max(np.abs(result-theta))),
                 initial_penalized_displacement_energy=float(.5*(start-theta)@h@(start-theta)))
    return result,audit


def closed_ring_obstruction(radius,neighbor_distance,neighbor_radius,margin):
    """A degree-one fixed-radius closed ring covers every angle.

If any open angular interval is forbidden, tangential reparameterization alone
cannot keep that degree and avoid the obstacle. Not a proof for variable offset,
arbitrary surfaces, disconnected strips, or changes of support topology.
"""
    low,high=exterior_arc(radius,neighbor_distance,neighbor_radius,margin)
    return dict(obstructed=bool(low>0 or high<2*np.pi),allowed_arc=[low,high],
                assumption='continuous degree-one closed ring on a fixed-radius cylinder')
