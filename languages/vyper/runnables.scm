; Gutter action on the constructor. The vyper-compile tag selects "Vyper: Compile".
(
  (function_definition
    name: (identifier) @run)
  (#eq? @run "__init__")
  (#set! tag vyper-compile)
)
