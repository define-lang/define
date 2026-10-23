//! Builds Python collections from one reused stack of elements, so that no
//! collection needs an allocation of its own.

use crate::node_construction::{Node, NodeTuple};
use pyo3::prelude::*;
use pyo3::types::{PyFrozenSet, PyString, PyTuple};
use std::marker::PhantomData;

/// The elements of the collections being built. A construct pushes its
/// elements after those of the constructs it belongs to, and takes them off
/// before it returns, so one stack serves every construct.
pub struct ElementStack<'py, Object> {
    py: Python<'py>,
    elements: Vec<Bound<'py, Object>>,
}

/// Where the elements of a collection whose elements are all `Element` start
/// on its stack. It is not `Copy`, so that each collection is finished
/// exactly once.
pub struct ElementsStart<Element> {
    index: usize,
    element: PhantomData<Element>,
}

impl<'py, Object> ElementStack<'py, Object> {
    pub const fn new(py: Python<'py>) -> Self {
        Self {
            py,
            elements: Vec::new(),
        }
    }

    pub const fn start<Element>(&self) -> ElementsStart<Element> {
        ElementsStart {
            index: self.elements.len(),
            element: PhantomData,
        }
    }
}

impl<'py> ElementStack<'py, PyAny> {
    // `_start` makes the element's type the one that its tuple holds.
    pub fn push<Element: Node<'py>>(
        &mut self,
        _start: &ElementsStart<Element>,
        element: impl Into<Element>,
    ) {
        self.elements.push(element.into().into_object());
    }

    pub fn finish_tuple<Element>(
        &mut self,
        start: ElementsStart<Element>,
    ) -> PyResult<NodeTuple<'py, Element>> {
        Ok(NodeTuple::new(PyTuple::new(
            self.py,
            self.elements.drain(start.index..),
        )?))
    }
}

impl<'py> ElementStack<'py, PyString> {
    // `_start` is the tuple or set that the text belongs to.
    pub fn push(&mut self, _start: &ElementsStart<PyString>, text: Bound<'py, PyString>) {
        self.elements.push(text);
    }

    pub fn finish_tuple(
        &mut self,
        start: ElementsStart<PyString>,
    ) -> PyResult<Bound<'py, PyTuple>> {
        PyTuple::new(self.py, self.elements.drain(start.index..))
    }

    pub fn finish_set(
        &mut self,
        start: ElementsStart<PyString>,
    ) -> PyResult<Bound<'py, PyFrozenSet>> {
        PyFrozenSet::new(self.py, self.elements.drain(start.index..))
    }
}
