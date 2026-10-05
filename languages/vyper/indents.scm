(_
  "["
  "]" @end) @indent

(_
  "{"
  "}" @end) @indent

(_
  "("
  ")" @end) @indent

(function_definition) @start.def

(if_statement) @start.if

(elif_clause) @start.elif

(else_clause) @start.else

(for_statement) @start.for

(event_definition) @start.event

(struct_definition) @start.struct

(interface_definition) @start.interface

(enum_definition) @start.enum

(flag_definition) @start.flag

(error_definition) @start.error
