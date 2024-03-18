# Add default index 0 for ByteAddressBuffer::Load

* Proposal: [Add default index 0 for ByteAddressBuffer::Load](ByteAddressBuffer_Load_with_default_index0.md)
* Author(s): [Xiang Li](https://github.com/python3kgae)
* Sponsor: TBD
* Status: **Under Consideration**


## Introduction

template<typename T>
T ByteAddressBuffer::Load(int Index)

into

template<typename T>
T ByteAddressBuffer::Load(int Index=0)


## Motivation


// Using TBuffers
struct S {
   float4 other_thing;
   float4x3 mBones[43];
};

TextureBuffer<S> foo : register(t0);

float4 TBuffer( float3 P : pos, uint bone_idx : idx) : SV_POSITION
{
    return mul( foo.mBones[bone_idx], P );
}

// Using Byte address buffers with same memory layout

ByteAddressBuffer b : register(t0);

float4 ByteAddress( float3 P : pos, uint bone_idx : idx ) : SV_POSITION
{
     // The index 0 is required here.
     float4x3 mTransform = {
       b.Load<T>(0).mBones[bone_idx];
     return mul( mTransform, P );
}


## Proposed solution

Add default index 0.
b.Load<T>(0) could be b.Load<T>() which is easier when replace TextureBuffer.

## Detailed design

Just add default value 0 when create the paramter for ByteAddressBuffer::Load.
