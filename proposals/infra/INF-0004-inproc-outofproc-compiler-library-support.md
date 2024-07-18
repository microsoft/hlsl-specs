<!-- {% raw %} -->

# In-process only or In-process and Out-of-process support for the compiler library

* Proposal: [0004](INF-0004-inproc-outofproc-compiler-library-support.md)
* Author(s): [Cooper Partin](https://github.com/coopp)
* Sponsor: [Cooper Partin](https://github.com/coopp)
* Status: **Under Consideration**
* Impacted Project(s): (Clang)

* Issues:

## Introduction

An effort is underway to bring compilation support into clang for HLSL based
shaders.  A C style library will be built to enable applications to compile
a shader from their own processes in addition to being able to launching the
clang process.

There are two proposed ways one could consume the shader compiler library and
compile a shader today.

* **In Process** - An application links against the shader compiler library to
bring in support for shader compilation as a static library
(full implementation) or a dynamic library. Compilation is performed within the
calling application's process.

* **Out of Process** - An application links against the shader compiler library and
uses the apis to compile which create one or more processes on the
application's behalf to compile one or more shaders. Compilation is performed
outside the calling application's process and isolated away to a worker
process.

In-Process must be supported because it is already a method that applications
use today to consume the DirectX Shader Compiler library.

The DirectX Shader library does not currently support being linked as a
static library.  It is a COM interface library that brings in compilation
support dynamically. This proposal does not take away the static library
support we already intend to build in clang HLSL compiler library.

This document is a discussion about an process design and to evaluate if
we need to build it immediately.

## Motivation

Help to scope down work for the new shader compiler library to the immediate
needs. Scoping down the required pieces of a large effort like bringing up full
hlsl support in clang is key to achieving success.

In-process support will be built but do we also need to build the out of
process design now or can this be deferred to a later milestone?

## Why Out of process support is even considered an option?

* Process creation on Windows based systems is expensive.  Launching clang.exe
over and over again to compile shaders becomes a lengthy operation on 
Windows platforms.

* Security concerns about compiling a shader in a process space that is
considered protected.  An out of process design would move that concern to an
isolated process.

* In-process support using multiple threads have known thread-safety concerns
for the clang compiler.  The clang compiler holds some state at compile time
and some of that state could leak to other compilation sessions if it is not
protected. This issue was also called out when an experiment called
[llvm-buildozer](https://reviews.llvm.org/D86351) was created.  The author was
interested in multiple threads re-entering the main compiler entry point in an
effort to reduce compilation times. The effort showed that the unsafe bits
could be fixed up and made thread safe allowing the experiment to be built.
I have not checked to see the thread safe fixed bits are in the current llvm
source.

   * In-process support with multiple threads is an option we need to
support as there are customers today that use the HLSL compiler library in 
that way. A separate instance of the library is created for each thread.
Multiple threads entering the same compiler library instance is not supported.

## Proposed solution

### What could an out-of-process design look like?

The architecture for an out of process design would behave in a similar way to
the MSBuild design. The system would function as a Process Pool.  This would
allow the HLSL compiler library to take advantage of systems that have
multiple processors, or multiple-core processors. A separate compiler process
is created for each available processor. For example, if the system has four
processors, then four compiler processes are created.

The process pool would be associated to an instance of the compiler library
and would live as long as that instance is alive.  Compilation requests will
be queued and the pool of processes would work through compilation requests.

Communication between the compiler library and the process pool will be done
using an IPC mechanism. This would most likely be named pipes with the pipe
name being unique to the process that it communicates with.

The application would call compiler apis that are really a stubbed 
interface of the in-process version which delegate the compilation work over
to the pool of processes.

Switching from in-proc use to out-of-proc use would not require api call 
changes giving the application the most flexibility to choose the 
environment they would like to compile their shaders.

### Error handling

If the HLSL compiler encounters an error during compilation or the compiler
process crashes, the rest of the compiler processes will continue on.
Error information will be communicated back to the caller about the issue and
the application will choose how to handle it.

### Open Questions

* Should the out of process architecture be built as a general purpose
system for others to be able to use?
   * I believe that is the correct approach for this design. There may be
     uses outside of shader compilation for this system.

## Detailed design

A detailed design of the out-of-process system has not been created.
There is an interesting example of an approach for a general purpose system
called 'Compiler Services'. This was presented as an option to support editors
and work with compiler databases. The proposal was called
[Clang C++ Services](https://github.com/chandlerc/llvm-designs/blob/master/ClangService.rst)

## Resources

## Acknowledgments

[Chris Bieneman](https://github.com/llvm-beanz)

<!-- {% endraw %} -->
