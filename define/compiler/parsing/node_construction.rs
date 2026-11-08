//! Constructs instances of the AST classes in `ast` without calling them.

use crate::ast::AstClasses;
use pyo3::exceptions::PyTypeError;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyNone, PyString, PyTuple, PyType};
use std::marker::PhantomData;

/// An AST class or a union of AST classes, as generated in `ast`.
pub trait Node<'py> {
    fn into_object(self) -> Bound<'py, PyAny>;
}

/// A value that can be a field of an AST node.
pub trait FieldValue<'py> {
    /// Returns the object that the field holds, giving the caller this
    /// value's reference to it.
    fn into_field_object(self, py: Python<'py>, classes: &AstClasses) -> Bound<'py, PyAny>;
}

impl<'py, Value: FieldValue<'py>> FieldValue<'py> for Option<Value> {
    fn into_field_object(self, py: Python<'py>, classes: &AstClasses) -> Bound<'py, PyAny> {
        match self {
            Some(value) => value.into_field_object(py, classes),
            None => PyNone::get(py).to_owned().into_any(),
        }
    }
}

impl<'py> FieldValue<'py> for bool {
    fn into_field_object(self, py: Python<'py>, _: &AstClasses) -> Bound<'py, PyAny> {
        PyBool::new(py, self).to_owned().into_any()
    }
}

impl<'py, Value> FieldValue<'py> for Bound<'py, Value> {
    fn into_field_object(self, _: Python<'py>, _: &AstClasses) -> Bound<'py, PyAny> {
        self.into_any()
    }
}

/// A `source_rendering.python.rendering.SourceLocation`.
#[derive(Clone)]
pub struct SourceLocation<'py>(Bound<'py, PyAny>);

impl<'py> SourceLocation<'py> {
    pub fn new(
        py: Python<'py>,
        location: source_rendering::SourceLocation,
        file_path: Option<&Bound<'py, PyString>>,
    ) -> PyResult<Self> {
        source_rendering_capsule::new_source_location(py, location, file_path).map(Self)
    }
}

impl<'py> Node<'py> for SourceLocation<'py> {
    fn into_object(self) -> Bound<'py, PyAny> {
        self.0
    }
}

impl<'py> FieldValue<'py> for SourceLocation<'py> {
    fn into_field_object(self, _: Python<'py>, _: &AstClasses) -> Bound<'py, PyAny> {
        self.0
    }
}

/// A Python tuple whose elements are all `Element`.
#[repr(transparent)]
pub struct NodeTuple<'py, Element> {
    tuple: Bound<'py, PyTuple>,
    element: PhantomData<Element>,
}

impl<'py, Element> NodeTuple<'py, Element> {
    /// Returns `tuple`, whose elements the caller knows are all `Element`.
    pub const fn new(tuple: Bound<'py, PyTuple>) -> Self {
        Self {
            tuple,
            element: PhantomData,
        }
    }
}

impl<'py, Element> FieldValue<'py> for NodeTuple<'py, Element> {
    fn into_field_object(self, _: Python<'py>, _: &AstClasses) -> Bound<'py, PyAny> {
        self.tuple.into_any()
    }
}

/// An AST class, and where each of its fields is in its instances.
pub struct ClassLayout<const FIELD_COUNT: usize> {
    class: Py<PyType>,
    allocate: ffi::allocfunc,
    /// The offset of each field's slot from the start of an instance.
    field_offsets: [ffi::Py_ssize_t; FIELD_COUNT],
}

impl<const FIELD_COUNT: usize> ClassLayout<FIELD_COUNT> {
    /// Loads the class `class_name` in `module`, whose fields are
    /// `field_names`.
    #[expect(
        unsafe_code,
        reason = "Only CPython's C API gives a class's allocator and the \
                  offsets of its fields."
    )]
    pub fn load(
        module: &Bound<'_, PyModule>,
        class_name: &str,
        field_names: [&str; FIELD_COUNT],
    ) -> PyResult<Self> {
        let class = module.getattr(class_name)?.cast_into::<PyType>()?;
        // SAFETY: `class` is a type object, which `PyType_Ready` gave an
        // allocator, inheriting `object`'s if it has none of its own.
        let Some(allocate) = (unsafe { (*class.as_type_ptr()).tp_alloc }) else {
            return Err(PyTypeError::new_err(format!(
                "{class_name} has no allocator"
            )));
        };
        let mut field_offsets = [0; FIELD_COUNT];
        for (offset, field_name) in field_offsets.iter_mut().zip(field_names) {
            let descriptor = class.getattr(field_name)?;
            // SAFETY: `PyMemberDescr_Type` is a static type object that
            // CPython never frees.
            let is_member_descriptor = unsafe {
                ffi::PyObject_TypeCheck(descriptor.as_ptr(), &raw mut ffi::PyMemberDescr_Type)
            } != 0;
            // msgspec stores each field in a slot, whose member descriptor
            // gives its offset. Anything else would make the cast below read
            // memory that is not a member descriptor.
            if !is_member_descriptor {
                return Err(PyTypeError::new_err(format!(
                    "{class_name}.{field_name} is not stored in a slot"
                )));
            }
            // SAFETY: `descriptor` is a member descriptor.
            let member =
                unsafe { (*descriptor.as_ptr().cast::<ffi::PyMemberDescrObject>()).d_member };
            // SAFETY: A member descriptor's member definition lives as long as
            // the class, which the module keeps.
            *offset = unsafe { (*member).offset };
        }
        Ok(Self {
            class: class.unbind(),
            allocate,
            field_offsets,
        })
    }

    /// Constructs an instance of the class whose fields are `fields`, in the
    /// order of the field names it was loaded with. Like msgspec's `__copy__`,
    /// it writes each field into its slot without calling the class, so
    /// `__post_init__` does not run.
    #[expect(
        unsafe_code,
        reason = "Calling the class would run `__post_init__`, which computes \
                  derived fields that the parser has already computed."
    )]
    #[expect(
        clippy::cast_ptr_alignment,
        reason = "CPython aligns each object slot of an instance for a pointer."
    )]
    pub fn construct<'py>(
        &self,
        py: Python<'py>,
        fields: [Bound<'py, PyAny>; FIELD_COUNT],
    ) -> PyResult<Bound<'py, PyAny>> {
        // SAFETY: `allocate` is the class's allocator. msgspec's classes have
        // no items.
        let allocated = unsafe { (self.allocate)(self.class.as_ptr().cast(), 0) };
        // SAFETY: The allocator returns a new reference to an instance whose
        // slots are all null, or null with an exception set.
        let instance = unsafe { Bound::from_owned_ptr_or_err(py, allocated)? };
        let start = instance.as_ptr().cast::<u8>();
        for (offset, field) in self.field_offsets.iter().zip(fields) {
            // SAFETY: `offset` is the offset of a slot in instances of the
            // class.
            let slot = unsafe { start.offset(*offset) }.cast::<*mut ffi::PyObject>();
            // SAFETY: The slot holds a reference to an object. It is null, so
            // the write drops no reference, and the instance takes the field's
            // reference. No other thread can read the slot before this
            // function returns the instance.
            unsafe {
                slot.write(field.into_ptr());
            }
        }
        Ok(instance)
    }
}
