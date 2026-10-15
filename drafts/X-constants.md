```define
define the constant<fqun:/name> {
    it is the literal</text>"foo".
}
```

Or I think actually better would be a concept of constant positions that can
have constructors or be set by config. Constants should probably only be
settable by compiler operations, or we should somehow make it apparent when
you've done something otherwise. We may need to specify runtime vs compile-time
constants.
