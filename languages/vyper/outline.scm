(function_definition
  "def" @context
  name: (identifier) @name) @item

(interface_sig
  "def" @context
  name: (identifier) @name) @item

(struct_definition
  "struct" @context
  name: (identifier) @name) @item

(event_definition
  "event" @context
  name: (identifier) @name) @item

(interface_definition
  "interface" @context
  name: (identifier) @name) @item

(enum_definition
  "enum" @context
  name: (identifier) @name) @item

(module
  (assignment
    left: (identifier) @name)) @item
