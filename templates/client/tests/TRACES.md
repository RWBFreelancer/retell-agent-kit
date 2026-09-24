# Traces

Write these before the prompt or the node text. One block per path.

```
### T-1  short name
Setup:    what the caller does
Path:     Node -> Node -> Node, naming each edge
Expect:   what is said, once, and in what order
Vars:     variable values at the end of the call
Fails if: the specific signature of failure
```
