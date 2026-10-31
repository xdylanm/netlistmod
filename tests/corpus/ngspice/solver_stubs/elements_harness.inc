* Definitions the elements_basic fixtures refer to (M7 solver stub, authored here; moved from
* the HARNESS constant of tests/solver/test_ngspice_solver_elements.py). rshunt gives every
* node a path to ground, so the toy circuits have an operating point.
.param rval=1k cval=1n lval=1u
.model RMODEL R rsh=100
.model newres R tc1=0.001
.model rmod R
.model cstd C cap=3n
.model CMODEL C cj=1e-4
.model indmod1 L ind=3n
.model DIODE1 D
.model DMOD D
.model 1n4148 D
.subckt MULTI 1 2 3 4 5
R1 1 2 1k
R2 3 4 1k
R3 5 0 1k
.ends
.subckt myfilter in out rval=100k cval=100n
R1 in out {rval}
C1 out 0 {cval}
.ends
.subckt sub a b r=1k file="none"
R1 a b {r}
.ends
.options rshunt=1e9
