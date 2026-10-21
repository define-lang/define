// TODO: Remove the cycle between this module and the generated `ast`, which
// uses this module's traits and implements its node constructors on
// `AstBuilder`, while this module uses `ast`'s `AstClasses` and
// `SourceLocation`. Moving the traits and argument types that `ast` needs into
// their own module, or generating the node constructors outside `ast`, would
// remove it.
use crate::ast::{AstClasses, SourceLocation};
use crate::scanner::{Position, SourceText};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyInt, PyNone, PyString, PyTuple, PyType};
use pyo3::{Borrowed, BoundObject, ffi};
use rustc_hash::FxHashMap;
use std::collections::hash_map::Entry;
use std::marker::PhantomData;
use std::ptr;

/// An AST class or a union of AST classes, as generated in `ast`.
pub trait Node<'py> {
    fn into_object(self) -> Bound<'py, PyAny>;
}

/// A value that can be passed to the constructor of an AST class.
pub trait PythonArgument<'py> {
    fn as_argument<'a>(
        &'a self,
        py: Python<'py>,
        classes: &'a AstClasses,
    ) -> Borrowed<'a, 'py, PyAny>
    where
        'py: 'a;
}

impl<'py, Value: PythonArgument<'py>> PythonArgument<'py> for Option<Value> {
    fn as_argument<'a>(
        &'a self,
        py: Python<'py>,
        classes: &'a AstClasses,
    ) -> Borrowed<'a, 'py, PyAny>
    where
        'py: 'a,
    {
        match self {
            Some(value) => value.as_argument(py, classes),
            None => PyNone::get(py).into_any(),
        }
    }
}

impl<'py> PythonArgument<'py> for bool {
    fn as_argument<'a>(&'a self, py: Python<'py>, _: &'a AstClasses) -> Borrowed<'a, 'py, PyAny>
    where
        'py: 'a,
    {
        PyBool::new(py, *self).into_any()
    }
}

impl<'py> PythonArgument<'py> for Bound<'py, PyString> {
    fn as_argument<'a>(&'a self, _: Python<'py>, _: &'a AstClasses) -> Borrowed<'a, 'py, PyAny>
    where
        'py: 'a,
    {
        self.as_borrowed().into_any()
    }
}

impl<'py> PythonArgument<'py> for Bound<'py, PyInt> {
    fn as_argument<'a>(&'a self, _: Python<'py>, _: &'a AstClasses) -> Borrowed<'a, 'py, PyAny>
    where
        'py: 'a,
    {
        self.as_borrowed().into_any()
    }
}

/// A `pathlib.PurePosixPath`.
#[derive(Clone)]
pub struct FilePath<'py>(Bound<'py, PyAny>);

impl<'py> FilePath<'py> {
    pub const fn new(path: Bound<'py, PyAny>) -> Self {
        Self(path)
    }
}

impl<'py> PythonArgument<'py> for FilePath<'py> {
    fn as_argument<'a>(&'a self, _: Python<'py>, _: &'a AstClasses) -> Borrowed<'a, 'py, PyAny>
    where
        'py: 'a,
    {
        self.0.as_borrowed()
    }
}

/// A Python tuple whose elements are all `Element`.
#[repr(transparent)]
pub struct NodeTuple<'py, Element> {
    tuple: Bound<'py, PyTuple>,
    element: PhantomData<Element>,
}

impl<'py, Element> PythonArgument<'py> for NodeTuple<'py, Element> {
    fn as_argument<'a>(&'a self, _: Python<'py>, _: &'a AstClasses) -> Borrowed<'a, 'py, PyAny>
    where
        'py: 'a,
    {
        self.tuple.as_borrowed().into_any()
    }
}

/// Where the elements of a tuple start on the builder's element stack. It is
/// not `Copy`, so that each tuple is finished exactly once.
pub struct TupleStart<Element> {
    index: usize,
    element: PhantomData<Element>,
}

/// Constructs the Python AST for one parse.
pub struct AstBuilder<'py, 'source> {
    py: Python<'py>,
    classes: &'static AstClasses,
    file_path: Option<FilePath<'py>>,
    /// The interned Python string for each distinct name in this parse.
    names: FxHashMap<&'source [u8], Bound<'py, PyString>>,
    /// The Python int for each line number, indexed by line number minus one.
    line_numbers: Vec<Bound<'py, PyInt>>,
    /// The elements of the tuples being built. A construct pushes its elements
    /// after any elements of the constructs it belongs to, and takes them off
    /// before it returns, so one stack serves every construct.
    tuple_elements: Vec<Bound<'py, PyAny>>,
}

impl<'py, 'source> AstBuilder<'py, 'source> {
    pub fn new(py: Python<'py>, file_path: Option<FilePath<'py>>) -> PyResult<Self> {
        Ok(Self {
            py,
            classes: AstClasses::get(py)?,
            file_path,
            names: FxHashMap::default(),
            line_numbers: Vec::new(),
            tuple_elements: Vec::new(),
        })
    }

    pub const fn py(&self) -> Python<'py> {
        self.py
    }

    pub const fn classes(&self) -> &'static AstClasses {
        self.classes
    }

    /// Calls `class` with `arguments`, passing the last ones by the keyword
    /// names in `keyword_names`.
    #[expect(
        unsafe_code,
        reason = "PyO3 passes keyword arguments only in a dict, which would \
                  be built for every node."
    )]
    pub fn construct<const COUNT: usize>(
        &self,
        class: &Py<PyType>,
        arguments: [Borrowed<'_, 'py, PyAny>; COUNT],
        keyword_names: Option<&Py<PyTuple>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let pointers = arguments.map(Borrowed::as_ptr);
        // Most generated constructors pass every argument by position, so they
        // pass `None` here. Each call inlines with its own `COUNT`, so for them
        // the keyword handling below compiles away to a constant argument count
        // and a null keyword-names pointer.
        let keyword_names = keyword_names.map(|names| names.bind(self.py));
        let keyword_count = keyword_names.map_or(0, PyTupleMethods::len);
        let keyword_names_pointer = keyword_names.map_or(ptr::null_mut(), Bound::as_ptr);
        // SAFETY: Vectorcall borrows the callable, the arguments, and the
        // keyword names only for the call, and `class`, `arguments`, and
        // `keyword_names` keep them alive until it returns. The keyword names
        // are a tuple of strings, one for each of the last `keyword_count`
        // arguments. The call returns a new reference, or null with an
        // exception set.
        unsafe {
            Bound::from_owned_ptr_or_err(
                self.py,
                ffi::PyObject_Vectorcall(
                    class.as_ptr(),
                    pointers.as_ptr(),
                    COUNT - keyword_count,
                    keyword_names_pointer,
                ),
            )
        }
    }

    /// Returns the interned Python string for the name `text`, creating it only
    /// the first time this parse sees that name.
    pub fn name(&mut self, text: SourceText<'source>) -> PyResult<Bound<'py, PyString>> {
        match self.names.entry(text.bytes) {
            Entry::Occupied(entry) => Ok(entry.get().clone()),
            Entry::Vacant(entry) => {
                let name = std::str::from_utf8(text.bytes).map_err(|error| {
                    PyValueError::new_err(format!("a name is not valid UTF-8: {error}"))
                })?;
                let name = PyString::intern(self.py, name);
                Ok(entry.insert(name).clone())
            }
        }
    }

    pub fn location(&mut self, start: Position, end: Position) -> PyResult<SourceLocation<'py>> {
        let line = self.line_number(start.line);
        let end_line = self.line_number(end.line);
        self.source_location(
            line,
            PyInt::new(self.py, start.column),
            end_line,
            // `end` is the position after the last character.
            PyInt::new(self.py, end.column - 1),
            self.file_path.clone(),
        )
    }

    fn line_number(&mut self, line: usize) -> Bound<'py, PyInt> {
        while self.line_numbers.len() < line {
            let next_line = self.line_numbers.len() + 1;
            self.line_numbers.push(PyInt::new(self.py, next_line));
        }
        self.line_numbers[line - 1].clone()
    }

    pub const fn start_tuple<Element>(&self) -> TupleStart<Element> {
        TupleStart {
            index: self.tuple_elements.len(),
            element: PhantomData,
        }
    }

    // `_start` makes the element's type the one that its tuple holds.
    pub fn push<Element: Node<'py>>(
        &mut self,
        _start: &TupleStart<Element>,
        element: impl Into<Element>,
    ) {
        self.tuple_elements.push(element.into().into_object());
    }

    pub fn finish_tuple<Element>(
        &mut self,
        start: TupleStart<Element>,
    ) -> PyResult<NodeTuple<'py, Element>> {
        Ok(NodeTuple {
            tuple: PyTuple::new(self.py, self.tuple_elements.drain(start.index..))?,
            element: PhantomData,
        })
    }
}
