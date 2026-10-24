//! The keywords, phrases, and punctuation of the grammar, grouped under the
//! section of the spec that defines them, in the spec's order.

// Parsing Define Source Code

pub const SPACE: u8 = b' ';
pub const LINE_FEED: u8 = b'\n';

// Comments

pub const COMMENT_START: u8 = b'#';

// Name Format

pub const NAME_CONTENT_START: u8 = b'<';
pub const NAME_CONTENT_END: u8 = b'>';
pub const COMPONENT_SEPARATOR: u8 = b':';
pub const PATH_SEPARATOR: u8 = b'/';
pub const POSITION: &[u8] = b"position";
pub const ACTION: &[u8] = b"action";
pub const VALUE: &[u8] = b"value";
pub const ENCODING: &[u8] = b"encoding";
pub const LITERAL: &[u8] = b"literal";
pub const OPERATION: &[u8] = b"operation";
pub const ENCODING_OPERATION: &[u8] = b"encoding_operation";
pub const VIEW: &[u8] = b"view";

// Statements

pub const TERMINATOR: u8 = b'.';

// Blocks

pub const OPEN_BRACE: u8 = b'{';
pub const CLOSE_BRACE: u8 = b'}';
/// What the grammar's `block_open` starts with.
pub const BLOCK_OPEN: &[u8] = &[SPACE, OPEN_BRACE];

// Defining Local Positions

pub const DEFINE_THE: &[u8] = b"define the ";
pub const DEFINE_THE_POSITION: &[u8] = b"define the position";
pub const IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE: &[u8] = b"it may only contain particles where";
pub const IT_HAS_THE: &[u8] = b"it has the";

// Position References

pub const CHAIN_SEPARATOR: &[u8] = b"::";

// Defining Potential Positions

pub const DEFINE_THE_POTENTIAL: &[u8] = b"define the potential ";
pub const DEFINE_THE_POTENTIAL_POSITION: &[u8] = b"define the potential position";

// Defining Value Qualities

pub const DEFINE_THE_POTENTIAL_VALUE: &[u8] = b"define the potential value";

// Defining Encodings

pub const DEFINE_THE_ENCODING: &[u8] = b"define the encoding";

// Defining Potential Literals

pub const DEFINE_THE_POTENTIAL_LITERAL: &[u8] = b"define the potential literal";

// Defining Potential Actions

pub const DEFINE_THE_POTENTIAL_ACTION: &[u8] = b"define the potential action";
pub const IT_HAPPENS_WHEN: &[u8] = b"it happens when";
pub const THE: &[u8] = b"the";
pub const THE_AND_SPACE: &[u8] = b"the ";
pub const THE_POSITION: &[u8] = b"the position";
pub const THE_ACTION: &[u8] = b"the action";
pub const SPACE_HAS_A_PARTICLE: &[u8] = b" has a particle";
pub const SPACE_AND_IT_DOES: &[u8] = b" and it does";

// Quality Implication Statements

pub const IT_ALSO_ASSIGNS_THE: &[u8] = b"it also assigns the";

// Creating Particles

pub const CREATE_A_PARTICLE_IN: &[u8] = b"create a particle in";

// Constructors

pub const THIS_PARTICLE_IS_CREATED: &[u8] = b"this particle is created";

// Moving Particles

pub const MOVE_THE_PARTICLE_IN: &[u8] = b"move the particle in";
pub const SPACE_TO: &[u8] = b" to";

// Destroying Particles

pub const DESTROY_THE_PARTICLE_IN: &[u8] = b"destroy the particle in";

// Destructors

pub const THIS_PARTICLE_IS_BEING_DESTROYED: &[u8] = b"this particle is being destroyed";

// Literals

/// The `"` that begins and ends literal content.
pub const LITERAL_CONTENT_DELIMITER: u8 = b'"';
/// The `\` that begins an escape in literal content.
pub const ESCAPE: u8 = b'\\';
/// The character after a `\` that stands for a line feed in literal content.
pub const ESCAPED_LINE_FEED: u8 = b'n';

// Setting Values

pub const SET_THE_VALUE_OF: &[u8] = b"set the value of";

// Value Operations

pub const DEFINE_THE_OPERATION: &[u8] = b"define the operation";
pub const DEFINE_THE_VIEW: &[u8] = b"define the view";
pub const IT_IS_READ: &[u8] = b"it is read";
pub const IT_IS_WRITTEN: &[u8] = b"it is written";
pub const IT_DOES: &[u8] = b"it does";
pub const EXECUTE_THE_ENCODING_OPERATION: &[u8] = b"execute the encoding operation";

// Executing Value Operations

pub const EXECUTE_THE: &[u8] = b"execute the";
pub const WITH: &[u8] = b"with";
pub const SPACE_LOOKING_AT: &[u8] = b" looking at";

// Encoding Operations

pub const DEFINE_THE_ENCODING_OPERATION: &[u8] = b"define the encoding_operation";
pub const EXECUTE_THE_COMPUTER_OPERATION: &[u8] = b"execute the computer operation";
