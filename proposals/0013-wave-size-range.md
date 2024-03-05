# Wave Size Range

* Proposal: [0013](0013-wave-size-range.md)
* Author(s): [Greg Roth](https://github.com/pow2clk)
* Sponsor: [Greg Roth](https://github.com/pow2clk)
* Status: **Under Consideration**
* Planned Version: Shader Model 6.8

## Introduction

Shader Model 6.6 included the ability to specify a wave size on a shader entry
 point in order to indicate either that a shader depends on or strongly prefers
 a specific wave size.
If that size of wave isn't available to the current hardware,
 shader will fail to load.
If that wave size is among those supported by the platform,
 it must be the one used when the shader is executed.
This enables creating custom shaders optimized for the wave size of a
 particularly interesting platform and loading them when possible.
Existing queries provide the developer with all the information necessary
 to determine what a platform supports,
 which should let them choose shaders accordingly.

## Motivation

Shader Model 6.6 provides no mechanism for specifying multiple wave sizes that a
 single shader might be able to support.
Consequently, if more than one target wave size is of interest, separate entry
 points will have to be created for each wave size.
These will each have to be compiled and shipped separately and, at run time,
 the appropriate shaders will have to be selected.
This increases the size of the shipped product and potentially slows down
 runtime shader loading.

Ranges of wave sizes are already present in areas of the D3D API.
The query to determine what wave sizes are supported takes a range and similar
 information is transmitted from the shader to the runtime, though not the
 driver.

## Proposed solution

Modifying the parameters of the `WaveSize` attribute that was introduced by
 Shader Model 6.6 to take additional parameters will allow the shader author to
 specify fully what the shader supports and what it prefers.

By adding an optional second `WaveSize` parameter, shader authors can provide
 two values that represent the range of wave sizes that the shader can support.
This allows the same shader to be used in the event of the availability of a
 wave size that the shader has optimized for specifically as well as other sizes
 that are supported, but might not be so optimal.

Some platforms that support a range of wave sizes might overlap with the range
 specified as supported by the shader in more than one value.
In these cases, the graphics driver has a choice of wave sizes,
 but it probably doesn't have the information needed to choose the best wave size.

To provide the needed information, the shader author could specify the
 preferred wave size in addition to the full range of acceptable values.
By adding an optional third `WaveSize` parameter, shader authors can specify the
 optimal wave size for a given shader in addition to the range of acceptable
 sizes.
This also preserves the ability to force the driver to choose your preferred
 wave size when multiples are available just as was done with the single value
 `WaveSize` attribute.

## Detailed Design

### HLSL additions

The existing `WaveSize` attribute gains a new variant:

```HLSL
[WaveSize(<minWaveSize>, <maxWaveSize>, [prefWaveSize])]
void main() ...
```

Where `minWaveSize` is the minimum wave size supported by the shader
 representing the beginning of the allowed range,
 `maxWaveSize` is the maximum wave size supported by the shader
 representing the end of the allowed range,
 and `prefWaveSize` is the optional preferred wave size representing the size
 expected to be the most optimal for this shader.

### DXIL Additions

The existing metadata `kDxilWaveSizeTag`(11)
 that takes only a single 32-bit integer constant is invalid in 6.8 shaders,
 but will continue to be supported in earlier shader model versions.

The new metadata `kDxilRangedWaveSizeTag`(23) takes a tuple
 of three 32-bit integers.
These values represent all potential parameters to `WaveSize`.
If all three values are non-zero, they represent the minimum, maximum,
 and preferred wave sizes respectively.
If only the first two values are non-zero, they represent the minimum
 and maximum respectively without a specified preferred size.
If only the first value is non-zero, it represents the legacy wave size as
 introduced in Shader Model 6.6 and previously represented by `kDxilWaveSizeTag`.
In this case, the single non-zero value is effectively minimum, maximum and
 preferred size in that it represents the only wave size supported by the shader.

|         Tag             | Constant |         Value           | Shader Models |
|-------------------------|----------|-------------------------|---------------|
|kDxilWaveSizeTag         |    11    |          i32            |     <6.8      |
|kDxilRangedWaveSizeTag   |    23    |MD list: (i32, i32, i32) |    >=6.8      |

### SPIR-V Additions

To represent the wave size range and preferred value in SPIR-V,
 a new `ExecutionMode` value would need to be defined for the `OpExecutionMode`
 instruction to allow specifying `SubgroupSize` with three operands instead of
 one.
Like the other formats, the location of the operands would indicate
 what each value represents, the first two being the min and max wave sizes and
 the third being the preferred wave size.

### Diagnostic Changes

#### New Errors

These are where new or slightly altered errors are produced:

* If any of the parameters of `WaveSize` are not compile-time constant
  power-of-two integers between 4 and 128 inclusive.
* If the minimum wave size value is greater than or equal to the max wave size
 as respectively specified by the first and second parameters in the `WaveSize`
 attribute.
* If the preferred wave size value indicated by the third parameter of
 `WaveSize` is not in the range specified by the first two parameters.
* If multiple `WaveSize` attributes are applied to the same entry point
 with different numbers or values of parameters,
 the existing error indicating an attribute conflict is produced.
* If more than three or fewer than one parameter is applied to `WaveSize`.

#### Validation Changes

Validation should confirm:

* The metadata `kDxilRangedWaveSizeTag` points to a tuple of exactly three
 elements.
* Each element of that tuple is a power-of-two integer between 4 and 128
 inclusive or zero.
* However, the first element (minimum wave size) is not zero.
* The first element (minimum wave size) is less than the second
 (maximum wave size).
* The third element (preferred wave size) is greater or equal to the first
 element (minimum wave size) and less than or equal to the second element
 (maximum wave size) or zero.
* Shaders with with versions less than 6.8 fail on shaders that use
 `kDxilRangedWaveSizeTag`.
* Shaders with versions greater than or equal to 6.8 fail on shaders that use
 `kDxilWaveSizeTag`.

### Runtime Additions

#### Runtime information

No additions are needed here.
The PSV0 runtime data structure already contains both
 `MinimumExpectedWaveLaneCount` and `MaximumExpectedWaveLaneCount` members that
 can be used to transmit the minimum and maximum values to the runtime.
The existing single wave size value will continue to set both of these values to
 that provided by the user.
The preferred value is not relevant to the runtime as it cannot result in
 shader loading failure.

#### Device Capability

As a required feature, devices supporting the Shader Model 6.8 are
 required to respect the wave size restrictions indicated by the wave size range
 metadata.

## Testing

### Correct Behavior Testing

Verify the following compiler output:

1. The one parameter variant of `WaveSize` correctly produces a metadata tuple
 pointed to by a `kDxilRangedWaveSizeTag` in the entry point attribute list with
 the single value as the first element and the last two elements set to zero.
 No `kDxilWaveSizeTag` should be produced.
2. The two parameter variant of `WaveSize` correctly produces a metadata tuple
 pointed to by a `kDxilRangedWaveSizeTag` in the entry point attribute list with
 the two values as the first two elements and the last element set to zero.
 No `kDxilWaveSizeTag` should be produced.
3. The three parameter variant of `WaveSize` correctly produces a metadata tuple
 pointed to by a `kDxilRangedWaveSizeTag` in the entry point attribute list with
 all three values in their respective element locations.
 No `kDxilWaveSizeTag` should be produced.
4. That the PSV0 `MinimumExpectedWaveLaneCount` and `MaximumExpectedWaveLaneCount`
  values reflect those provided for the wave size range.

Note that the above must all use literal values for the parameters on account of
 other compile-time constants being broken due to DXC bug
 [#2188](https://github.com/microsoft/DirectXShaderCompiler/issues/2188).

#### Diagnostics Testing

1. Use the following invalid parameters each parameter location to `WaveSize`
  and ensure that an appropriate error is produced:
   1. Negative power-of-two integer
   2. Floating-point value
   3. non-compile-time constant integer
   4. Power-of-two integer less than 4
   5. Power-of-two integer greater than 128
   6. A non-power-of-two integer between 4 and 128
2. Add the following invalid `WaveSize` attributes to an compute shader entry
  point and ensure that an appropriate error is produced:
   1. No parameter list
   2. An empty parameter list "()"
   3. Four parameters
3. Try the following invalid `WaveSize` parameter value combinations and ensure
  that an appropriate error is produced:
   1. The minimum wave size is equal to the maximum
   2. The minimum wave size is greater than the maximum
   3. The preferred wave size is a value outside of the specified range
4. Combine multiples of the 1, 2 and 3 parameter `WaveSize` attribute variants
  with different values on the same entry point and ensure that an attribute
  conflict error is produced.

### Validation Testing

Test that the following produce validation errors:

1. The wave size range tag pointing to anything but a tuple of 3.
2. A tuple value is not an integer.
3. A range tuple value is -4, 0, 1, 2, 3, 127, 129, or 256.
4. A preferred tuple value is -4, 1, 2, 3, 127, 129, or 256.
5. The minimum wave size value is equal to the maximum, but otherwise valid.
6. The minimum wave size value is greater than the maximum, but otherwise valid.
7. The preferred wave size is outside the specified range, but otherwise valid.
8. Multiple metadata `kDxilRangedWaveSizeTag`s are in the same compiled shader.
9. A metadata `kDxilWaveSizeTag` is used with 1.8 or greater validation.
10. Explicit validator versions before 1.8 used with `kDxilRangedWaveSizeTag`s.

### Execution Testing

The runtime responsibilities are to reject shaders that have wave size
 requirements that can't be supported and to use the preferred value when
 possible even if another size is available.

The platform's supported wave size range should first be queried using
 `WaveLaneCountMin` and `WaveLaneCountMax` from the
 `D3D12_FEATURE_DATA_D3D12_OPTIONS1` D3D structure.
This platform range should be used to craft a shader requested range that
 verifies that the platform accepts and rejects all the shaders it should.

Ensure that the following shader range with platform range combinations are
 accepted:

* The shader range minimum is the same as the platform range maximum.
* The shader range maximum is the same as the platform range minimum.
* The shader range is a superset of the platform range, but only by one power of
  two value if possible.
* The shader range is the full 4-128.

Ensure that the following shader range with platform combinations are rejected:

* The shader range minimum is one power of two greater than the platform
  range maximum.
* The shader range maximum is one power of two less than the platform range
  minimum.

For platforms that support more than one wave size, platform treatment of the
 preferred wave size is needed.
When available to the platform, the preferred value must be used.
When not available, but others in the range are, the shader should still be
 accepted.
The wave size used can be queried using `WaveGetLaneCount` and fed back to the
 test to determine that the preferred wave size was used.

For each wave size in the platform range,
 ensure that the following shader range, preferred value, and platform range
 combinations are accepted and use the preferred value:

* The  preferred value and shader maximum is equal to the current platform
  range value and the shader minimum is one power of two less than the platform
  minimum.
* The preferred value and shader minimum is equal to the current platform
  range value and the shader maximum is one power of two more than the platform
  maximum.
* The shader range is the full 4-128 and the preferred value is the current
  platform range value.

For each wave size in the platform range,
 ensure that the following shader range, preferred value, and platform range
 combinations are accepted:

* The shader maximum is equal to the current platform range value and the
  preferred value and shader minimum is one power of two less than the platform
  minimum.
* The shader minimum is equal to the current platform range value and the
  preferred value and shader maximum is one power of two more than the platform
  maximum.
* The shader range is the full 4-128 and the preferred value is one power of two
  less than the current platform range value.
* The shader range is the full 4-128 and the preferred value is one power of two
  greater than the current platform range value.

## Alternatives considered

Useful as it is, the preferred wave size parameter adds some level of testing,
 diagnostic, and other implementation complexity.
It wasn't part of the original discussions that motivated this feature,
 but it is necessary to maintain one aspect of the original `WaveSize` behavior.
In addition to allowing the platform to reject wave sizes that are unsupported
 at all, the single-value `WaveSize` attribute tells the platform which wave
 size to choose among however many options the platform offers.
Without the preferred wave size, there wouldn't be a way to specify this
 preference and the platform might choose arbitrarily among the supported values.

Instead of modifying the existing attribute, an additional range attribute taking
 only two parameters might be provided to specify the range while keeping the
 existing `WaveSize` attribute to indicate the preferred wave size.
This has the advantage of keeping the syntax and semantics of the existing
 attribute unaltered.
However, the name of the attribute is not really consistent with a preferred
 value.
If we could do it over and replace them with attributes named `WaveSizeRange` and
 `WaveSizeOptimal` or similar, the two attribute approach would be clean and
 of clear intent.
Introducing new values like that and deprecating recently added old ones is
 more likely to cause confusion than employing the broadly named `WaveSize` to
 include all the information about wave sizing that a shader might need to
 specify to the runtime system.

Additionally, the existing `WaveSize` could be kept unaltered and a new
 attribute with new spelling such as `WaveSizeRange` could take either two or
 three parameters and represent the range with the optional preferred size.
The only issue here is that it complicates correctness checking a bit where
 shaders that might employ both are concerned.
The simple solution would be to allow only one of either `WaveSize` or
 `WaveSizeRange`.
Mild aesthetic preference ultimately opted to reuse the existing attribute.

## Acknowledgements

This document received invaluable contributions and feedback from various Microsoft
 team members and our partners.

Special thanks:

* Alan Baker
* Chris Bieneman
* Joshua Batista
* Martin Fuller
* Amar Patel
* Damyan Pepper
* Tex Riddell
