; Later patterns override earlier ones.

(comment) @comment

(string) @string
(escape_sequence) @string.escape

[
  (integer)
  (float)
] @number

[
  (true)
  (false)
] @boolean

(none) @constant.builtin

[
  "assert"
  "break"
  "continue"
  "def"
  "del"
  "elif"
  "else"
  "for"
  "from"
  "if"
  "import"
  "lambda"
  "pass"
  "raise"
  "return"
  "while"
  "as"
  "in"
  "is"
  "not"
  "and"
  "or"
  "event"
  "struct"
  "enum"
  "flag"
  "error"
  "interface"
  "log"
  "extcall"
  "staticcall"
  "type"
  "async"
] @keyword

[
  "-"
  "-="
  "!="
  "*"
  "**"
  "**="
  "*="
  "/"
  "//"
  "//="
  "/="
  "&"
  "&="
  "%"
  "%="
  "^"
  "^="
  "+"
  "->"
  "+="
  "<"
  "<<"
  "<<="
  "<="
  "="
  ":="
  "=="
  ">"
  ">="
  ">>"
  ">>="
  "|"
  "|="
  "~"
  "@"
] @operator

[
  "."
  ","
  ":"
  ";"
] @punctuation.delimiter

[
  "("
  ")"
  "["
  "]"
  "{"
  "}"
] @punctuation.bracket

(identifier) @variable

((identifier) @constant
  (#match? @constant "^_*[A-Z][A-Z0-9_]*$"))

((identifier) @constant.builtin
  (#match? @constant.builtin "^(ZERO_ADDRESS|EMPTY_BYTES32|MAX_INT128|MIN_INT128|MAX_INT256|MIN_INT256|MAX_UINT256)$"))

((identifier) @variable.special
  (#match? @variable.special "^(self|msg|block|tx|chain)$"))

(type
  (identifier) @type)

(generic_type
  (identifier) @type)

((identifier) @type.builtin
  (#match? @type.builtin "^(bool|address|decimal|string|bytes|String|Bytes|HashMap|DynArray|uint(8|16|24|32|40|48|56|64|72|80|88|96|104|112|120|128|136|144|152|160|168|176|184|192|200|208|216|224|232|240|248|256)|int(8|16|24|32|40|48|56|64|72|80|88|96|104|112|120|128|136|144|152|160|168|176|184|192|200|208|216|224|232|240|248|256)|bytes(1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31|32))$"))

(function_definition
  name: (identifier) @function)

(interface_sig
  name: (identifier) @function
  mutability: (identifier) @keyword)

((function_definition
  name: (identifier) @constructor)
  (#eq? @constructor "__init__"))

(call
  function: (identifier) @function)

(call
  function: (attribute
    attribute: (identifier) @function))

((call
  function: (identifier) @keyword)
  (#match? @keyword "^(public|immutable|constant|transient)$"))

(decorator
  (identifier) @attribute)

(decorator
  (call
    function: (identifier) @attribute))

(struct_definition
  name: (identifier) @type)

(event_definition
  name: (identifier) @type)

(enum_definition
  name: (identifier) @type)

(flag_definition
  name: (identifier) @type)

(error_definition
  name: (identifier) @type)

(interface_definition
  name: (identifier) @type)

(parameters
  (identifier) @variable.parameter)

(typed_parameter
  . (identifier) @variable.parameter)

(default_parameter
  name: (identifier) @variable.parameter)

(typed_default_parameter
  name: (identifier) @variable.parameter)

(attribute
  attribute: (identifier) @property)

((module
  (assignment
    left: (identifier) @keyword))
  (#eq? @keyword "implements"))
