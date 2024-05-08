* Proposal: [0004](0004-binding-prefixes.md)
* Author(s): [Joshua Batista](https://github.com/bob80905)
* Sponsor: TBD
* Status: **Under Consideration**
* Impacted Project(s): (LLVM)

*During the review process, add the following fields as needed:*

* PRs: [#87578](https://github.com/llvm/llvm-project/pull/87578)
* Issues: [#57886](https://github.com/llvm/llvm-project/issues/57886)

## Introduction

There's a specific set of valid types that can be bound as a resource in HLSL.
When invalid types are bound to resources, helpful diagnostics need to be emitted
so that the user knows why the bound type is invalid, or why the binding prefix
isn't correct.

## Motivation

There are currently several cases in which diagnostics that are related to
binding prefixes are out of date or invalid. For example, in the case of:

`float b : register(u4);`
an error will be emitted recommending the use of the 'b, c, or i' binding
prefix, however these prefixes are no longer in support. Additionally,
it is possible the user is unaware that this resource won't actually be
used, but the compiler doesn't communicate that to the user.
It would be great for any HLSL developer to immedaitely have answers to 
the following questions:
For any valid resource type that needs to be bound, what are the set of
valid binding prefixes for that resource, and what are all the possible 
diagnostics that can be emitted if the resource is given a binding 
prefix that isn't in the set of valid binding prefixes?
The design below aims to specify the answer to these questions.

## Proposed solution
Firstly, the most common case is when a resource type that is not a 
user-defined type is bound as a resource. Any resource will have an 
associated ResourceAttr attribute, from which we can determine the 
resource class and resource kind. These two inputs are sufficient to
determine the expected binding prefix, and any other binding prefix
will result in an error. The recommended binding prefix will be
suggested in the diagnostic. The table below specifies what binding 
prefix will be expected for any resource type that falls under the
specified resource class. 

| Resource Class | Binding Prefix | Diagnostic |
|-|-|-|
| Sampler | s | "Object type '%0' with resource class "Sampler" expects binding prefix 's', but binding prefix '%1' was given." |
| SRV | t | "Object type '%0' with resource class "SRV" expects binding prefix 't', but binding prefix '%1' was given." |
| UAV | u | "Object type '%0' with resource class "UAV" expects binding prefix 'u', but binding prefix '%1' was given." |
| CBuffer | b |  "Object type '%0' with resource class "CBuffer" expects binding prefix 'b', but binding prefix '%1' was given." |

There are certain resource kinds within the SRV resource
class that are "sampleable". These resources are typically
prefixed with "Texture" in actual HLSL source. So, there will
be a special check to see whether the candidate resource is 
prefixed with "Texture", and if so, the "s" binding prefix will
also be permitted for that resource.

If the given candidate resource is a user-defined type (UDT), then further
analysis is necessary. The first step is to gather all registers that
are being bound to this declaration, and collect the binding prefixes
that are being specified. The UDT must have at least one valid resource
that can be bound to the provided binding prefix. If not, an error must be
emitted stating that "No resource contained in struct '%0' can be bound
to binding prefix '%1'". There are no issues if a UDT has more resources
than there are register binding statements, the resources will be bound to
the next available space automatically, and so compilation can succeed.
Additionally, a singular resource can be bound multiple times to different
spaces, so multiple binding prefixes are allowed for a single resource.
Below is a table that represents the different behaviors that could arise
given some examples of different UDT's:

| UDT | Binding statements | Diagnostic |
|-|-|-|
| struct Foo {<br>  float f;<br>  Buffer<float> Buf;<br>  RWBuffer<float> RWBuf;<br>};| register(t0) : register(s0); | None. Success because Buf gets bound to t0 and RWBuf gets bound to s0, and f is skipped. 
| struct Foo {<br>  float f;<br>  Buffer<float> Buf;<br>  RWBuffer<float> RWBuf;<br>  RWBuffer<float> RWBuf2;<br>};<br> | register(t0) : register(s0); | None. Success because Buf gets bound to t0  and RWBuf gets bound to s0, and f is skipped. RWBuf2 gets assigned to s1  even though there is no explicit binding for s1. |
| struct Foo {<br>  float f;<br>  Buffer<float> Buf;<br>}; <br>| register(t0) : register(s0); | None. Success because Buf gets bound to t0. Buf will also be bound to s0.|
| struct Foo {<br>  struct Bar {<br>    RWBuffer<int> a;<br>    };<br>    Bar b;<br>}; | register(t0) | None. Success because Bar, the struct within Foo, has a valid resource that can be bound to t0. |
| struct Foo {<br>  float f;<br>}; <br>| register(t0) | DefaultError warning. "UDT resource 'Foo' does not contain an applicable resource type for binding prefix 't'"|
| struct Foo {<br>  struct Bar {<br>      float f;<br>    }<br>    Bar b;<br>};<br> | register(t0) | DefaultError warning. "UDT resource 'Foo' does not contain an applicable resource type for binding prefix 't'"|

Finally, if the candidate type is not a valid resource type or not a
UDT, the final case will be entered. If the resource is among any
numeric or non-intangible types, there is only one exception where it can
be treated as a resource. That is, for all non-intangible types, types
that obviously are not, or cannot contain, a valid resource type (types 
like int, float, float4, etc), the only valid binding prefix is 'b', which
adheres to legacy behavior. All other binding prefixes applied to such
a type will emit an error diagnostic that "the given type '%0' cannot be
bound as a resource". If the binding prefix is 'b', a warning will be 
emitted instead, that will be treated as an error by default:
"binding prefix 'b' used for resource type '%0', which cannot be used
as a resource". Below are some examples:

| non-intangible type | Binding statements | Diagnostic |
|-|-|-|
| `float f` | register(t0) | "error: 'float' is an invalid resource type for binding prefix 't'." |
| `float f` | register(b0) | "warning: binding prefix 'b' used for resource type 'float', which cannot be used as a resource" |



## Detailed design

All the compiler has to work with is a Decl object. From the Decl object, 
the ResourceAttr attribute can be fetched, with which the resource 
class can be determined. Once this is known, we then check if the resource
type is a user-defined type or if it is a standard resource type. If the 
resource type is among the standard resource types (e.g., cbuffer, tbuffer,
RWBuffer, etc.), then the binding prefix is checked for validity. The resource
is also checked for sampleability (i.e., is it a texture resource?). If there is
an incompatibility between resource class and binding prefix, a diagnostic will
be emitted. Otherwise, the resource is a user-defined type, and so the type needs
to be validated to see whether it can properly be assigned to the geiven binding 
prefix. If the UDT does not have at least one resource that matches the given binding 
prefixes, then an error will be emitted. The only remaining case is when there
is no resource attribute, which implies the type is non-intangible. In this case,
if the type is strictly numeric, the only acceptable binding prefix is 'b', which 
is legacy behavior. In this case, a warning will be emitted that will be treated as 
an error by default, which states that a numeric type is not usable as a resource. 
Any other binding prefix will cause an error to be emitted, stating that the given 
type cannot be bound as a resource.
Legacy behavior can be allowed with the --Wno-disallow-legacy-binding-rules
flag. When this flag is active, and legacy behavior is present, a warning will 
be emitted instead of an error.

Below is a flowchart that describes the process that is used to determine
what kind of diagnostic to emit in each case:

```mermaid
flowchart TD
A[Type T bound to 
binding prefix p] --> B{Does T have or 
contain any type
with the ResourceAttr
attribute?}
B -- Yes -->C{Is T a UDT?}
B -- No --> M{Is T non-intangible?}
C -- Yes -->D{Does T contain
at least one 
valid resource 
for p?}
C -- No -->G{"Is T sampleable 
(is it a Texture* resource?)"}
D -- Yes -->E[No error]
D -- No -->F[error: UDT resource '&ltT&gt'
does not contain an 
applicable resource 
type for binding 
prefix '&ltp&gt']
G -- Yes -->H{Is the binding 
prefix 't' or 's'?}
G -- No --> I{Was the binding 
prefix given 's'?}
H -- Yes -->L{Was the binding 
prefix given 's'?}
H -- No --> J[error: Object type '&ltT&gt' 
with resource class 
'&ltresource class&gt' expects 
binding prefix 't' or 's', 
but binding prefix 
'&ltp&gt' was given.]
I -- Yes --> V[DefaultError warning: 
binding prefix 's' 
can only be used on 
sampleable resource types, 
but resource type &ltT&gt 
was given. Disable with
--Wno-disallow-legacy-binding-rules]
I -- No -->K{Is T a valid resource
class for the given
prefix 'p'?}
K -- Yes -->Q[No error]
K -- No --> R[error: Object type '&ltT&gt'
with resource class 
'&ltresource class&gt' expects
binding prefix 
'&ltexpected binding prefix&gt', 
but binding prefix 
'&ltp&gt' was given.]
L -- Yes -->O[warning: resource type 
&ltT> is being sampled.]
L -- No -->P[No error.]
M -- Yes -->N{Is the given 
binding prefix 'b'?}
M -- No --> S[Assert, this should 
be impossible]
N -- Yes -->T[warning: binding prefix 
'b' used for resource type 
'&ltT&gt', which cannot 
be used as a resource."]
N -- No -->U[error: &ltT&gt is an invalid 
resource type for 
binding prefix '&ltp&gt']
```


## Alternatives considered (Optional)

## Acknowledgments (Optional)
* Tex Riddell
* Chris Bieneman
* Justin Bogner
<!-- {% endraw %} -->