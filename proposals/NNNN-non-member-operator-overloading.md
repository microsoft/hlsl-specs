# Non-member Operator Overloading

## Instructions

* Proposal: [NNNN](NNNN-non-member-operator-overloading.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: 202x
* Related Proposal(s): [0006 Reference Types](0006-reference types.md)

## Introduction

HLSL 202x introduced operator overloading for member operators of user defined
data types. Only supporting member operators has some drawbacks, specifically
defining binary operators where the LHS is a built-in type is impossible,
additionally scoping operators to namespaces is also impossible.

## Motivation

Beyond common use cases where global operators are nice to have, users adopting
HLSL 2021 have provided feedback that global operator overloading would be a
significant benefit.

HLSL 2021's introduction of short circuiting boolean operators users have been
forced to translate their code that operates on HLSL vector types to use the
new `select`, `and` and `or` intrinsics. We believe the new intrinsics are the
right step for the language in removing ambiguity and clearly expressing code
meaning. Global operator overloading provides an opportunity for the language to
remain clear and unambiguous, while allowing users to define custom operators
that allow them to not migrate legacy code.

## Proposed solution

This change requires fully adopting C++ rules for operator overload resolution
and supporting defining global and namespace scoped operator overloads. The
limitations currently in place on operator overloading (disallowing overloading
operators that idiomatically return references) will remain in effect on
non-member operators as well unless the restrictions are lifted as proposed in
[0006 Reference Types](0006-reference types.md).

Because this solution should not break existing code, it could also be enabled
under HLSL 2021 as an extension.

## Alternatives considered

One considered option was to roll back the HLSL 2021 removal of vector
operators. Operator short circuiting was introduced in HLSL 2021 to reduce
behavioral differences between HLSL and C/C++. With operator short circuiting
vector operator aren't intuitive because they can't short circuit.

Having scalar operators short circuit and vector operators not was also
considered. The argument against that approach is that having two code
representations that look the same but behave differently is unintuitive. This
gets more unintuitive when you consider that with the introduction of templates
the same literal line of code could be used for both vector and scalar
conditionals with different behavior.

For these reasons, this proposal posits that HLSL 2021's decision is the correct
approach for the language. This proposal gives users the ability to introduce
source compatibility if they choose, but at their own maintenance expense.

## Acknowledgments

This proposal is the result of conversations with users and teammates. Thank you
everyone who contributed feedback on HLSL 2021.
