# Dxil Debug Printf

* Proposal: [NNNN](NNNN-debug-printf.md)
* Author(s): [Jiao Lu](https://github.com/jiaolu)
* Sponsor: TBD
* Status: **Under Consideration**

## Introduction

Add new dxil op to allow c/c++ like *printf* intrinsic instructions can be
generated in the dxil sourced from hlsl.

## Motivation

As the new shader models, i.e. RayTracing, RayQuery, Workgraph, and more complex
algorithms and structure emerges in recent time, we meet many more requirements of 
debugging capabilities of hlsl coding in game, application and driver development.

The dxil counterpart spirv has a similar feature, 
[NonSemantic.DebugPrintf extention](https://github.com/KhronosGroup/SPIRV-Registry/blob/main/nonsemantic/NonSemantic.DebugPrintf.asciidoc)
to generate DebugPrintf spirvOp sourced from hlsl/glsl. Based on the spirvOp
extention, some vendor drivers and Valve lunarG has 
[debug printf layer](https://github.com/KhronosGroup/Vulkan-ValidationLayers/blob/main/docs/debug_printf.md)
to dump printf expression, "hlsl/glsl variables" into stdio or file.

## Proposed solution

The printf expression in hlsl mostly like this example.
```c++ hlsl:


void main() {
    printf("hello");
    printf("Variables are: %d %d %.2f", 1u, 2u, 1.5f);
}

```

The format specifier generally follow the c/c++ format specifiers as here, https://www.geeksforgeeks.org/format-specifiers-in-c/,
Though how the final string representation after printf output is implementation dependent.


DirectXCompiler at present can parse "printf" statement in hlsl as dx.hl.op 
instructions,
```
dx.hl.op..void (i32, i8*, ...);
```
The printf format string, the second argument of the printf instruction of 
dx.hl.op is a global *constant* variable or a GEP constant expression.

The parsing is called from ast frontend into the 
HandleTranslationUnit-->TranslatePrintf.The function *TranslatePrintf* itself
 is empty implementation.

The implementation of debug printf dxil op will be

1) assign new dxil op code to the debug printf.
2) Finished the TranslatePrintf implementation, create dxil op instruction with 
a proper dxil op code, and replace dx.hl.op. the dxil op instruction function 
will be a variable arguments function.


## Detailed design

1. Add a option to enable printf dxil op generation to dxc, try to separate hlsl code
for debugging purpose and for production purpose. The printf option is disabled by default, 
and the printf instructions in hlsl will be report a error without a printf option.
2. We should not support dynamic string variable, a string variable content.
retrieved from buffer. The string variable should be explicitly defined and can 
be retrieved directly/indirectly from global constant variable.
3. The format string input to the dx.hl.op..void, could be llvm constant 
expression, we need to retrieve global variable from the constant expression.
4. The validation for the dxil overloading checking should be ignored. Because 
of printf variable arguments, there is no definite function type can be validated.
5. dxc will validate matching relation between format specifiers and arguments. 
If the number of arguments and number of format specifiers mismatch, dxc will 
produce error messages, If their types mismatch, dxc will report a warning messages.
