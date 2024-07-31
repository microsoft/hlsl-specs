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

### Why have an api at all?  Why not just run clang.exe yourself?

Before diving into any details we should discuss why we even need an
api at all.  Why can't clients just execute the clang.exe with options
and compile their shaders that way?  They can and they will. Launching clang
to compile a shader will be supported.

A design requirement that cannot be satisfied with just executing clang with a 
command-line is _include handlers_. An include handler is a way for clients to
hook into the compilation process and dynamically load dependencies when
needed. We have already been asked by a game studio to support this feature.
This can only be achieved if there is an api to support adding these handlers.

### Overview of api hosting differences

Here are two common ways an api can be loaded and used.

* **In Process** - An application calls an api that loads compilation support
into the application's process. All work is performed within the application's
process.

* **Out of Process** - An application calls an api that launches one or more
processes to perform the compilation. All work is performed outside the
calling application's process.

## Motivation

### Why prefer an out of process solution?

* Security is a concern when compiling a shader in a process space that is
considered protected.  An out of process design would move that concern to an
isolated process.

* Running multiple instances of clang In-process across multiple threads has
known thread-safety concerns for the clang compiler. The clang compiler holds
some state at compile time and some of that state could leak to other
compilation sessions if it is not protected. This issue was also called out
when an experiment called [llvm-buildozer](https://reviews.llvm.org/D86351)
was created.  The author was interested in multiple threads re-entering the
main compiler entry point in an effort to reduce compilation times. The effort
showed that the unsafe bits could be fixed up and made thread safe allowing
the experiment to be built. I have not checked to see the thread safe fixed
bits are in the current llvm source.

* Cleanup between compiler invocations. Destroying a process and bringing it
back up ensures that any state leaked or leftover from a previous compilation
will be cleaned up.

* Handling of catastrophic errors avoids taking down the calling process. The
clang compiler is known to abort in certain conditions which would take down
a process if they hosted the compiler in-process. The worker process will be
taken down not the application with an out-of-process design.

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

## Detailed design

A detailed design of the out-of-process system has not been created.
There is an interesting example of an approach for a general purpose system
called 'Compiler Services'. This was presented as an option to support editors
and work with compiler databases. The proposal was called
[Clang C++ Services](https://github.com/chandlerc/llvm-designs/blob/master/ClangService.rst)

## Alternatives considered

In-proc only was not considered here because of the issue involving
catastrophic error conditions which can takes down the calling process.
This is also why there is no in-proc + out-of-proc proposal.

### What if in-process becomes a requirement at a later time?

An in-process solution can easily be built because the support code that
performs compilation will have already been refactored out to be called
during the out of process development effort.

## Acknowledgments

[Chris Bieneman](https://github.com/llvm-beanz)

<!-- {% endraw %} -->
