<!-- {% raw %} -->

# DirectX Container Symbol and String Table

## Instruction* Proposal: [XXXX](xxxx-symbol-and-string-table.md)
* Author(s): [Chris Bieneman](https://github.com/llvm-beanz)
* Sponsor: [Chris Bieneman](https://github.com/llvm-beanz)
* Status: **Under Consideration**
* Planned Version: SM 6.8+

## Introduction

This proposal introduces two new parts to the DXIL container format to capture a
symbol table and file-level string table.

## Motivation

As the usage of DXIL libraries expands and we seek to make DXIL linking better
supported having a symbol table for DXIL libraries will allow the linker to more
efficiently choose whether or not a library needs to be loaded during linking.
Additionally this change adds a separate DXIL part to contain a file-wide string
table. Today DXIL container parts each contain their own string tables. Those
string tables can (and do) have duplicated strings.

## Proposed solution

Add two new parts to the DXIL container format with magic IDs `SYM0` and `STR0`
which will represent the symbol table and string table respectively.

### Symbol Table

The new symbol table is designed to match the Windows PE/COFF symbol table and
uses the Windows PE/COFF bigobj symbol structures and enumeration values. There
are two significant differences from the PE/COFF symbol table:

1. The DXIL symbol table will initially only contain exported function symbols.
2. The DXIL symbol table will be in its own part, whereas in PE/COFF files it is usually not in a separate section.

As with all DXIL container data, all data in the symbol table is little-endian encoded.

### String Table

The new string table utilizes the Windows PE/COFF string table formatting. The
string table is preceded by a 4-byte little-endian unsigned integer denoting its
size followed by a table of null-terminated strings.

## Detailed design

### Symbol Table

The new symbol table is comprised of little-endian encoded symbol structures
based on the C definition below:

```c
struct Symbol {
  union {
    uint8_t ShortName[8];
    struct {
      uint32_t Zeros;
      uint32_t NameOffset;
    } LongName;
  } Name;
  uint32_t Value;
  uint32_t SectionIndex;
  uint8_t BaseType;
  uint8_t ComplexType;
  uint8_t StorageClass;
  uint8_t Unused; // DXIL will not support auxiliary symbols.
};
```

The values for the `BaseType`, `ComplexType`, and `StorageClass` fields will be
inherited from the PE/COFF specification. See the Appendix below for the full
PE/COFF enum specification.

The initial implementation of the DXIL symbol table will only include defined
exported function symbols. It will not include any unresolved external symbols
or any non-function symbols.

All initial symbols will have the `BaseType` set to `IMAGE_SYM_TYPE_NULL`, the
`ComplexType` set to `IMAGE_SYM_DTYPE_FUNCTION`, and the `StorageClass` set to
`IMAGE_SYM_CLASS_EXTERNAL`. This denotes externally exported symbols with full
definitions in the DXIL.

The `SectionIndex` for all symbols that refer to the DXIL part will be the index
of the DXIL part in the part offset list from the container header.

#### Encoding of Short Names

Windows COFF symbols encode names 8 characters or less in length directly in the
symbol. Names longer than 8 characters get encoded in the string table and a
32-bit unsigned little-endian offset gets encoded in the symbol in the second
4-bytes of the `Name`. DXIL symbols will match this behavior.

### String Table

The new string table will be encoded as a Windows PE/COFF string table. The
table will start with a 4-byte little-endian unsigned integer encoding the table
size. It will be followed by null-terminated strings for each string. The full
table will be padded to a multiple of 4-bytes.

The string table may be unoptimized or utilize a suffix-packing optimization to
save storage. This is up to the implementation to decide. This means there is no
guarantee that strings do not overlap.

For example, the strings "bar" and "foobar" might be packed into the string
table so that the string table only contains "foobar\0". The string "foobar"
would be assigned offset 4, and the string "bar" would be assigned offset 7
(both offsets are 4-byte incremented for the preceding size field).

The maximum size of the string table is `UINT32_MAX`, although other offsets in
the DX Container file may not be able to handle string tables significantly
smaller than that.

### DXIL Validation

The DXIL validator will validate an appropriate number of exported symbols for
the target profile. The table below describes the maximum number of exported
symbols per shader profile:

| Profile        | Maximum Number of Symbols               |
|----------------|-----------------------------------------|
| Pixel          | 1                                       |
| Vertex         | 1                                       |
| Geometry       | 1                                       |
| Hull           | 2                                       |
| Domain         | 1                                       |
| Compute        | 1                                       |
| Library        | UINT32_MAX / sizeof(Symbol) = 214748364 |
| Mesh           | 1                                       |
| Amplification  | 1                                       |

The effective maximum allowable symbol count for Library shaders is
significantly lower since many offsets in the DX Container file are 32-bit. It
is expected that things will break if the file size exceeds `UINT32_MAX`.

### Other Considerations

This change has no impact on the HLSL language representation. It has no
interaction with existing language features or C++ features. It has no source
compatibility impact or impact on SPIR-V.

## Alternatives considered (Optional)

We could continue extending custom data structures in the DXIL Container to
capture new data. This change is likely overkill for our immediate needs,
however it is more forward proof and will enable a longer term move to adopt
existing binary formats and conventions.

## Appendix 1: PE/COFF Constants

The following constants are inherited from the PE/COFF specification:

```c
enum SymbolStorageClass {
    SSC_Invalid = 0xff,

    IMAGE_SYM_CLASS_END_OF_FUNCTION  = -1,  ///< Physical end of function
    IMAGE_SYM_CLASS_NULL             = 0,   ///< No symbol
    IMAGE_SYM_CLASS_AUTOMATIC        = 1,   ///< Stack variable
    IMAGE_SYM_CLASS_EXTERNAL         = 2,   ///< External symbol
    IMAGE_SYM_CLASS_STATIC           = 3,   ///< Static
    IMAGE_SYM_CLASS_REGISTER         = 4,   ///< Register variable
    IMAGE_SYM_CLASS_EXTERNAL_DEF     = 5,   ///< External definition
    IMAGE_SYM_CLASS_LABEL            = 6,   ///< Label
    IMAGE_SYM_CLASS_UNDEFINED_LABEL  = 7,   ///< Undefined label
    IMAGE_SYM_CLASS_MEMBER_OF_STRUCT = 8,   ///< Member of structure
    IMAGE_SYM_CLASS_ARGUMENT         = 9,   ///< Function argument
    IMAGE_SYM_CLASS_STRUCT_TAG       = 10,  ///< Structure tag
    IMAGE_SYM_CLASS_MEMBER_OF_UNION  = 11,  ///< Member of union
    IMAGE_SYM_CLASS_UNION_TAG        = 12,  ///< Union tag
    IMAGE_SYM_CLASS_TYPE_DEFINITION  = 13,  ///< Type definition
    IMAGE_SYM_CLASS_UNDEFINED_STATIC = 14,  ///< Undefined static
    IMAGE_SYM_CLASS_ENUM_TAG         = 15,  ///< Enumeration tag
    IMAGE_SYM_CLASS_MEMBER_OF_ENUM   = 16,  ///< Member of enumeration
    IMAGE_SYM_CLASS_REGISTER_PARAM   = 17,  ///< Register parameter
    IMAGE_SYM_CLASS_BIT_FIELD        = 18,  ///< Bit field
    /// ".bb" or ".eb" - beginning or end of block
    IMAGE_SYM_CLASS_BLOCK            = 100,
    /// ".bf" or ".ef" - beginning or end of function
    IMAGE_SYM_CLASS_FUNCTION         = 101,
    IMAGE_SYM_CLASS_END_OF_STRUCT    = 102, ///< End of structure
    IMAGE_SYM_CLASS_FILE             = 103, ///< File name
    /// Line number, reformatted as symbol
    IMAGE_SYM_CLASS_SECTION          = 104,
    IMAGE_SYM_CLASS_WEAK_EXTERNAL    = 105, ///< Duplicate tag
    /// External symbol in dmert public lib
    IMAGE_SYM_CLASS_CLR_TOKEN        = 107
  };

  enum SymbolBaseType {
    IMAGE_SYM_TYPE_NULL   = 0,  ///< No type information or unknown base type.
    IMAGE_SYM_TYPE_VOID   = 1,  ///< Used with void pointers and functions.
    IMAGE_SYM_TYPE_CHAR   = 2,  ///< A character (signed byte).
    IMAGE_SYM_TYPE_SHORT  = 3,  ///< A 2-byte signed integer.
    IMAGE_SYM_TYPE_INT    = 4,  ///< A natural integer type on the target.
    IMAGE_SYM_TYPE_LONG   = 5,  ///< A 4-byte signed integer.
    IMAGE_SYM_TYPE_FLOAT  = 6,  ///< A 4-byte floating-point number.
    IMAGE_SYM_TYPE_DOUBLE = 7,  ///< An 8-byte floating-point number.
    IMAGE_SYM_TYPE_STRUCT = 8,  ///< A structure.
    IMAGE_SYM_TYPE_UNION  = 9,  ///< An union.
    IMAGE_SYM_TYPE_ENUM   = 10, ///< An enumerated type.
    IMAGE_SYM_TYPE_MOE    = 11, ///< A member of enumeration (a specific value).
    IMAGE_SYM_TYPE_BYTE   = 12, ///< A byte; unsigned 1-byte integer.
    IMAGE_SYM_TYPE_WORD   = 13, ///< A word; unsigned 2-byte integer.
    IMAGE_SYM_TYPE_UINT   = 14, ///< An unsigned integer of natural size.
    IMAGE_SYM_TYPE_DWORD  = 15  ///< An unsigned 4-byte integer.
  };

  enum SymbolComplexType {
    IMAGE_SYM_DTYPE_NULL     = 0, ///< No complex type; simple scalar variable.
    IMAGE_SYM_DTYPE_POINTER  = 1, ///< A pointer to base type.
    IMAGE_SYM_DTYPE_FUNCTION = 2, ///< A function that returns a base type.
    IMAGE_SYM_DTYPE_ARRAY    = 3, ///< An array of base type.

    /// Type is formed as (base + (derived << SCT_COMPLEX_TYPE_SHIFT))
    SCT_COMPLEX_TYPE_SHIFT   = 4
  };
```

The code snippet above is included from DXC's copy of
[include/llvm/Support/COFF.h](https://github.com/microsoft/DirectXShaderCompiler/blob/main/include/llvm/Support/COFF.h).


<!-- {% endraw %} -->
