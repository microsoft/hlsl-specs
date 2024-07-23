<!-- {% raw %} -->

# Support for in-process, Out-of-process, or both for the c style compiler api

* Proposal: [NNNN](INF-NNNN-inproc-outofproc-compiler-api-support.md)
* Author(s): [Cooper Partin](https://github.com/coopp)
* Sponsor: [Cooper Partin](https://github.com/coopp)
* Status: **Under Consideration**
* Impacted Project(s): (Clang)

* Issues:

## Introduction

An effort is underway to bring compilation support into clang for HLSL based
shaders.  A C style api will be built to enable applications to compile
a shader from their own processes in addition to being able to launching the
clang process.

This document is to propose building only the out-of-process support which
gives the caller a more performant and secure solution.

Visual Studio uses an out of process architecture for compilation which helps
better utilize the power of the machine performing the compilation as well as
isolating the code editor from any crashes that may occur during compilation.

### Overview of api hosting differences
Here are two common ways a library can be loaded and used.

* **In Process** - An application calls an api that loads compilation support
into the application's process. All work is performed within the application's
process.

* **Out of Process** - An application calls an api that launches one or more
processes to perform the compilation. All work is performed outside the
calling application's process.

## Motivation

### Why prefer an out of process solution?

* Process creation on Windows based systems is expensive.  Launching clang.exe
over and over again to compile shaders becomes a lengthy operation on 
Windows platforms.

* Security is a concern when compiling a shader in a process space that is
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

## Proposed solution

### What could an out-of-process design look like?

The architecture for an out of process design will behave in a similar way to
the MSBuild design. The system functions as a Process Pool.  This allows the
the compilation work to take advantage of systems that have multiple
processors, or multiple-core processors. A separate compiler process
is created for each available processor. For example, if the system has four
processors, then four compiler processes are created.

The process pool will be associated to an instance of the compiler library
and will live as long as that instance is alive.  Compilation requests will
be queued and the pool of processes that work through compilation requests.

Communication between with the process pool will be done using a named pipe
IPC mechanism. Pipe names will be unique to the process that is being
communicated with. Results are communicated back over the IPC mechanism.

### Error handling

If the HLSL compiler encounters an error during compilation or the compiler
process crashes, the rest of the compiler processes will continue on.
Error information is communicated back over the IPC mechanism to the caller
and the application will choose how to handle it.

### What if in-process becomes a requirement at a later time?

If an in process solution becomes a requirement, it can easily be built
because the support code that performs compilation will have already been
refactored out to be called by the out of process design.

### Open Questions

* Should the portions of the out of process architecture be built as a general
purpose system for others in the llvm project to be able to use in their own
systems?

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
