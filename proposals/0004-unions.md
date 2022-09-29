# Unions

* Proposal: [0004](0004-unions.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x

## Introduction

Introduce C++ Union data types into HLSL.

## Motivation

Unions were planned for HLSL 2021 but missed the feature window.

## Proposed solution

Union data types are defined in *\[class.union\]*of the ISO C++ language
specification. HLSL 202x introduces a compliant implementation with some HLSL
specific clarifications.

* Following C++ Unions are always sized large enough to contain their largest
  member type.
* Union members cannot have HLSL semantics applied to them.
* Union objects in buffer layouts are aligned as elements of their
  most-restrictive member type.
* Union objects in struct layouts behave as defined in C++.
* Union objects cannot have semantics applied to them.
* Union's cannot have user-defined constructors or destructors until the
  language supports them for other user defined data types (See:
  [0007](0007-constructors.md)).

## Acknowledgments

Special thanks to [Dan Brown](https://github.com/danbrown-amd), and Meghana
Thatishetti (Unknown GitHub ID), for their contributions to this implementation.
