We need to be able to check dimension-point existence modularly, which means you
_have_ to specify constraints on whether or not DPs are occupied. I think this
is fine for any position that the action _cares_ about, because that's how the
real universe would work---it would have responses to presence or absence, and
in our case, the response can simply be "go away". One could also do
`require that / or else` to fix it.
