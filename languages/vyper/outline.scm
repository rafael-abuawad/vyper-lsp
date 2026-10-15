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

(flag_definition
  "flag" @context
  name: (identifier) @name) @item

(error_definition
  "error" @context
  name: (identifier) @name) @item

((module
  (assignment
    left: (identifier) @name) @item)
  (#not-any-of? @name "implements" "initializes" "exports" "uses"))

(import_statement
  "import" @context
  name: (_) @name) @item

(import_from_statement
  "from" @context
  module_name: (_) @name) @item
