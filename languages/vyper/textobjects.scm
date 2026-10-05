(comment)+ @comment.around

(function_definition
  body: (_) @function.inside) @function.around

(interface_definition
  body: (_) @class.inside) @class.around

(struct_definition
  body: (_) @class.inside) @class.around

(event_definition
  body: (_) @class.inside) @class.around

(enum_definition
  members: (_) @class.inside) @class.around

(flag_definition
  members: (_) @class.inside) @class.around

(error_definition
  body: (_) @class.inside) @class.around
