# global
import ivy
from hypothesis import assume, strategies as st
import random

# local
import ivy_tests.test_ivy.helpers as helpers
from ivy_tests.test_ivy.helpers import handle_frontend_test


# --- Helpers --- #
# --------------- #


def _filter_dtypes(input_dtype):
    assume(("bfloat16" not in input_dtype) and ("float16" not in input_dtype))


@st.composite
def _generate_prelu_arrays(draw):
    arr_size = draw(helpers.ints(min_value=2, max_value=5))
    dtype = draw(helpers.get_dtypes("float", index=1, full=False))
    input = draw(
        helpers.array_values(
            dtype=dtype[0], shape=(arr_size), min_value=0, max_value=10
        )
    )
    weight = draw(
        helpers.array_values(dtype=dtype[0], shape=(1,), min_value=0, max_value=1.0)
    )
    input_weight = input, weight
    return dtype, input_weight


@st.composite
def _glu_arrays(draw):
    dtype = draw(helpers.get_dtypes("float", index=1, full=False))
    shape = draw(st.shared(helpers.ints(min_value=1, max_value=5)))
    shape = shape * 2
    input = draw(helpers.array_values(dtype=dtype[0], shape=(shape, shape)))
    dim = draw(st.shared(helpers.get_axis(shape=(shape,), force_int=True)))
    return dtype, input, dim


@st.composite
def _x_and_scaled_attention(draw, dtypes):
    dtype = draw(dtypes)
    num_queries = draw(helpers.ints(min_value=2, max_value=4))
    num_keys = draw(helpers.ints(min_value=2, max_value=4))
    feat_dim = draw(helpers.ints(min_value=2, max_value=4))
    batch_size = draw(helpers.ints(min_value=1, max_value=2))
    q_shape = (batch_size,) + (num_queries,) + (feat_dim,)
    k_shape = (batch_size,) + (num_keys,) + (feat_dim,)
    v_shape = (batch_size,) + (num_keys,) + (feat_dim,)
    mask_shape = (batch_size,) + (num_queries,) + (num_keys,)

    query = draw(
        helpers.array_values(
            dtype=dtype[0],
            shape=q_shape,
            min_value=0,
            max_value=1e2,
            large_abs_safety_factor=7,
            small_abs_safety_factor=7,
            safety_factor_scale="linear",
        )
    )
    key = draw(
        helpers.array_values(
            dtype=dtype[0],
            shape=k_shape,
            min_value=0,
            max_value=1e2,
            large_abs_safety_factor=7,
            small_abs_safety_factor=7,
            safety_factor_scale="linear",
        )
    )
    value = draw(
        helpers.array_values(
            dtype=dtype[0],
            shape=v_shape,
            min_value=0,
            max_value=1e2,
            large_abs_safety_factor=7,
            small_abs_safety_factor=7,
            safety_factor_scale="linear",
        )
    )
    mask = draw(
        helpers.array_values(
            dtype="bool",
            shape=mask_shape,
        )
        | st.none()
    )
    return dtype, query, key, value, mask


@st.composite
def mha_forward_args(draw, dtypes):
    dtype = draw(dtypes)
    embed_dim = draw(helpers.ints(min_value=2, max_value=4))
    batch_size = draw(helpers.ints(min_value=1, max_value=2)) * 3
    seq_len = draw(helpers.ints(min_value=2, max_value=4))
    shape = (
        seq_len,
        batch_size,
        embed_dim,
    )

    heads = draw(helpers.ints(min_value=1, max_value=4))
    head_dim = embed_dim // heads
    if head_dim * heads != embed_dim:
        heads = 1
        head_dim = embed_dim

    if dtype[0] == "float32":
        is_causal = False
    else:
        is_causal = draw(helpers.array_bools(size=1))[0]

    q = draw(
        helpers.array_values(dtype=dtype[0], shape=shape, min_value=0.1, max_value=1)
    )
    k = draw(
        helpers.array_values(dtype=dtype[0], shape=shape, min_value=0.1, max_value=1)
    )
    v = draw(
        helpers.array_values(dtype=dtype[0], shape=shape, min_value=0.1, max_value=1)
    )
    in_proj_weight = draw(
        helpers.array_values(
            dtype=dtype[0],
            min_value=0.1,
            max_value=1,
            shape=(embed_dim * 3, embed_dim),
        )
    )
    in_proj_bias = draw(
        helpers.array_values(
            dtype=dtype[0],
            min_value=0.1,
            max_value=1,
            shape=(embed_dim * 3,),
        )
    )

    if random.randint(0, 1) == 0:
        use_separate_proj_weight = True
        q_proj_weight = draw(
            helpers.array_values(
                dtype=dtype[0],
                min_value=0.1,
                max_value=1,
                shape=(embed_dim, embed_dim),
            )
        )
        k_proj_weight = draw(
            helpers.array_values(
                dtype=dtype[0],
                min_value=0.1,
                max_value=1,
                shape=(embed_dim, embed_dim),
            )
        )
        v_proj_weight = draw(
            helpers.array_values(
                dtype=dtype[0],
                min_value=0.1,
                max_value=1,
                shape=(embed_dim, embed_dim),
            )
        )
    else:
        use_separate_proj_weight = False
        q_proj_weight = None
        k_proj_weight = None
        v_proj_weight = None

    out_proj_weight = draw(
        helpers.array_values(
            dtype=dtype[0],
            min_value=0.1,
            max_value=1,
            shape=(embed_dim, embed_dim),
        )
    )
    out_proj_bias = draw(
        helpers.array_values(
            dtype=dtype[0],
            min_value=0.1,
            max_value=1,
            shape=(embed_dim,),
        )
    )
    bias_k = random.choice(
        [
            draw(
                helpers.array_values(
                    dtype=dtype[0],
                    min_value=0.1,
                    max_value=1,
                    shape=(embed_dim,),
                )
            ),
            None,
        ]
    )
    bias_v = bias_k

    if bias_k is None:
        static_k = random.choice(
            [
                draw(
                    helpers.array_values(
                        dtype=dtype[0],
                        min_value=0.1,
                        max_value=1,
                        shape=(batch_size * heads, seq_len, head_dim),
                    )
                ),
                None,
            ]
        )
        static_v = static_k
    else:
        static_k = None
        static_v = None

    attn_mask = ivy.ones((seq_len, seq_len), dtype=dtype[0])
    key_padding_mask = random.choice(
        [
            ivy.random_normal(shape=(seq_len, seq_len), dtype=dtype[0]) > 0,
            None,
        ]
    )

    return (
        dtype,
        q,
        k,
        v,
        heads,
        use_separate_proj_weight,
        embed_dim,
        in_proj_weight,
        in_proj_bias,
        out_proj_weight,
        out_proj_bias,
        q_proj_weight,
        k_proj_weight,
        v_proj_weight,
        bias_k,
        bias_v,
        static_k,
        static_v,
        attn_mask,
        key_padding_mask,
        is_causal,
    )


# --- Main --- #
# ------------ #


# celu
@handle_frontend_test(
    fn_tree="torch.nn.functional.celu",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    alpha=helpers.floats(min_value=0.1, max_value=1.0, exclude_min=True),
    test_inplace=st.booleans(),
    test_with_out=st.just(False),
)
def test_torch_celu(
    *,
    dtype_and_input,
    alpha,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
        alpha=alpha,
    )


# elu
@handle_frontend_test(
    fn_tree="torch.nn.functional.elu",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    alpha=helpers.floats(min_value=0.1, max_value=1.0, exclude_min=True),
    test_inplace=st.booleans(),
    test_with_out=st.just(False),
)
def test_torch_elu(
    *,
    dtype_and_input,
    alpha,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
        alpha=alpha,
    )


# elu_
@handle_frontend_test(
    fn_tree="torch.nn.functional.elu_",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    alpha=helpers.floats(min_value=0.1, max_value=1.0, exclude_min=True),
)
def test_torch_elu_(
    *,
    dtype_and_input,
    alpha,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        test_values=False,
        input=input[0],
        alpha=alpha,
    )


# gelu
@handle_frontend_test(
    fn_tree="torch.nn.functional.gelu",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
        max_value=1e04,
    ),
    approximate=st.sampled_from(["none", "tanh"]),
)
def test_torch_gelu(
    *,
    dtype_and_x,
    approximate,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
        rtol=1e-02,
        atol=1e-02,
        approximate=approximate,
    )


# glu
@handle_frontend_test(
    fn_tree="torch.nn.functional.glu",
    dtype_input_dim=_glu_arrays(),
)
def test_torch_glu(
    *,
    dtype_input_dim,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input, dim = dtype_input_dim
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
        dim=dim,
    )


# gumbel_softmax
@handle_frontend_test(
    fn_tree="torch.nn.functional.gumbel_softmax",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    tau=st.floats(min_value=0),
    hard=st.booleans(),
    eps=st.floats(min_value=0, max_value=1),
    dim=st.integers(),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_gumbel_softmax(
    *,
    dtype_and_x,
    tau,
    hard,
    eps,
    dim,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        test_values=False,
        logits=x[0],
        tau=tau,
        hard=hard,
        eps=eps,
        dim=dim,
    )


# hardshrink
@handle_frontend_test(
    fn_tree="torch.nn.functional.hardshrink",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    lambd=helpers.floats(min_value=0, max_value=1, exclude_min=True),
)
def test_torch_hardshrink(
    *,
    dtype_and_input,
    lambd,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
        lambd=lambd,
    )


# hardsigmoid
@handle_frontend_test(
    fn_tree="torch.nn.functional.hardsigmoid",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_hardsigmoid(
    *,
    dtype_and_input,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
    )


# hardswish
@handle_frontend_test(
    fn_tree="torch.nn.functional.hardswish",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
        safety_factor_scale="log",
    ),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_hardswish(
    *,
    dtype_and_input,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
    )


# hardtanh
@handle_frontend_test(
    fn_tree="torch.nn.functional.hardtanh",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    max_val=st.floats(min_value=0, max_value=1, exclude_min=True),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_hardtanh(
    *,
    dtype_and_x,
    max_val,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    max_min = max_val, -max_val
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
        min_val=max_min[1],
        max_val=max_min[0],
    )


# hardtanh_
@handle_frontend_test(
    fn_tree="torch.nn.functional.hardtanh_",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    max_val=st.floats(min_value=0, max_value=1, exclude_min=True),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_hardtanh_(
    *,
    dtype_and_x,
    max_val,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    max_min = max_val, -max_val
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        test_values=False,
        input=x[0],
        min_val=max_min[1],
        max_val=max_min[0],
    )


# leaky_relu
@handle_frontend_test(
    fn_tree="torch.nn.functional.leaky_relu",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    alpha=st.floats(min_value=0.0, max_value=1.0, exclude_min=True),
    test_inplace=st.booleans(),
    test_with_out=st.just(False),
)
def test_torch_leaky_relu(
    *,
    dtype_and_x,
    alpha,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
        rtol=1e-02,
        atol=1e-02,
        negative_slope=alpha,
    )


# leaky_relu_
# ToDo test for value test once inplace testing implemented
@handle_frontend_test(
    fn_tree="torch.nn.functional.leaky_relu_",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    alpha=st.floats(min_value=0, max_value=1, exclude_min=True),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_leaky_relu_(
    *,
    dtype_and_x,
    alpha,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        test_values=False,
        input=x[0],
        negative_slope=alpha,
    )


# local_response_norm
@handle_frontend_test(
    fn_tree="torch.nn.functional.local_response_norm",
    dtype_x_and_axis=helpers.dtype_values_axis(
        available_dtypes=helpers.get_dtypes("float"),
        min_num_dims=3,
        force_int_axis=True,
        valid_axis=True,
    ),
    size=helpers.ints(min_value=3, max_value=10),
    alpha=helpers.floats(min_value=1e-4, max_value=1e-3),
    beta=helpers.floats(min_value=0.5, max_value=2.0),
    k=helpers.ints(min_value=0, max_value=1),
)
def test_torch_local_response_norm(
    *,
    dtype_x_and_axis,
    size,
    alpha,
    beta,
    k,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    dtype, x, axis = dtype_x_and_axis
    _filter_dtypes(dtype)
    helpers.test_frontend_function(
        input_dtypes=dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
        size=size,
        alpha=alpha,
        beta=beta,
        k=k,
    )


# log_softmax
@handle_frontend_test(
    fn_tree="torch.nn.functional.log_softmax",
    dtype_x_and_axis=helpers.dtype_values_axis(
        available_dtypes=helpers.get_dtypes("float"),
        min_num_dims=1,
        max_axes_size=1,
        force_int_axis=True,
        valid_axis=True,
    ),
    dtypes=helpers.get_dtypes("float", none=False, full=False),
)
def test_torch_log_softmax(
    *,
    dtype_x_and_axis,
    dtypes,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x, axis = dtype_x_and_axis
    ivy.set_backend(backend_fw)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
        dim=axis,
        _stacklevel=3,
        dtype=ivy.as_ivy_dtype(dtypes[0]),
    )
    ivy.previous_backend()


# logsigmoid
@handle_frontend_test(
    fn_tree="torch.nn.functional.logsigmoid",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
)
def test_torch_logsigmoid(
    *,
    dtype_and_x,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
    )


# mish
@handle_frontend_test(
    fn_tree="torch.nn.functional.mish",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    test_inplace=st.booleans(),
    test_with_out=st.just(False),
)
def test_torch_mish(
    *,
    dtype_and_input,
    fn_tree,
    frontend,
    on_device,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
    )


# multi_head_attention_forward
@handle_frontend_test(
    fn_tree="torch.nn.functional.multi_head_attention_forward",
    dtype_mha_args=mha_forward_args(
        dtypes=helpers.get_dtypes("valid"),
    ),
    add_zero_attn=st.just(False),
    dropout_p=st.sampled_from([0.0, 0.1, 0.2]),
    training=st.booleans(),
    need_weights=st.booleans(),
    average_attn_weights=st.booleans(),
    test_with_out=st.just(False),
)
def test_torch_multi_head_attention_forward(
    *,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    dtype_mha_args,
    add_zero_attn,
    dropout_p,
    training,
    need_weights,
    average_attn_weights,
    backend_fw,
):
    (
        dtype,
        q,
        k,
        v,
        heads,
        use_separate_proj_weight,
        embed_dim,
        in_proj_weight,
        in_proj_bias,
        out_proj_weight,
        out_proj_bias,
        q_proj_weight,
        k_proj_weight,
        v_proj_weight,
        bias_k,
        bias_v,
        static_k,
        static_v,
        attn_mask,
        key_padding_mask,
        is_causal,
    ) = dtype_mha_args

    helpers.test_frontend_function(
        input_dtypes=dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        test_values=not training or dropout_p == 0.0,
        query=q,
        key=k,
        value=v,
        embed_dim_to_check=embed_dim,
        num_heads=heads,
        in_proj_weight=in_proj_weight,
        in_proj_bias=in_proj_bias,
        bias_k=bias_k,
        bias_v=bias_v,
        add_zero_attn=add_zero_attn,
        dropout_p=dropout_p,
        out_proj_weight=out_proj_weight,
        out_proj_bias=out_proj_bias,
        training=training,
        key_padding_mask=key_padding_mask,
        need_weights=need_weights,
        attn_mask=attn_mask,
        use_separate_proj_weight=use_separate_proj_weight,
        q_proj_weight=q_proj_weight,
        k_proj_weight=k_proj_weight,
        v_proj_weight=v_proj_weight,
        static_k=static_k,
        static_v=static_v,
        average_attn_weights=average_attn_weights,
        is_causal=is_causal,
    )


# normalize
@handle_frontend_test(
    fn_tree="torch.nn.functional.normalize",
    dtype_x_and_axis=helpers.dtype_values_axis(
        available_dtypes=helpers.get_dtypes("float"),
        min_num_dims=1,
        max_axes_size=1,
        force_int_axis=True,
        valid_axis=True,
    ),
    p=helpers.ints(min_value=2, max_value=5),
)
def test_torch_normalize(
    *,
    dtype_x_and_axis,
    p,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    dtype, x, axis = dtype_x_and_axis
    _filter_dtypes(dtype)
    helpers.test_frontend_function(
        input_dtypes=dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
        p=p,
        dim=axis,
        eps=1e-12,
    )


# prelu
@handle_frontend_test(
    fn_tree="torch.nn.functional.prelu",
    dtype_input_and_weight=_generate_prelu_arrays(),
)
def test_torch_prelu(
    *,
    dtype_input_and_weight,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    dtype, inputs = dtype_input_and_weight
    _filter_dtypes(dtype)
    helpers.test_frontend_function(
        input_dtypes=dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=inputs[0],
        weight=inputs[1],
    )


# relu
@handle_frontend_test(
    fn_tree="torch.nn.functional.relu",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    test_inplace=st.booleans(),
    test_with_out=st.just(False),
)
def test_torch_relu(
    dtype_and_input,
    frontend,
    test_flags,
    fn_tree,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        input=input[0],
    )


# relu6
@handle_frontend_test(
    fn_tree="torch.nn.functional.relu6",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("numeric"),
    ),
    test_inplace=st.booleans(),
    test_with_out=st.just(False),
)
def test_torch_relu6(
    *,
    dtype_and_input,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
    )


# relu_
@handle_frontend_test(
    fn_tree="torch.nn.functional.relu_",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    test_with_out=st.just(False),
)
def test_torch_relu_(
    dtype_and_input,
    frontend,
    test_flags,
    fn_tree,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        input=input[0],
    )


# rrelu
@handle_frontend_test(
    fn_tree="torch.nn.functional.rrelu",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    lower=helpers.floats(min_value=0, max_value=0.5, exclude_min=True),
    upper=helpers.floats(min_value=0.5, max_value=1.0, exclude_min=True),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_rrelu(
    *,
    dtype_and_input,
    lower,
    upper,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
        lower=lower,
        upper=upper,
    )


# rrelu_
@handle_frontend_test(
    fn_tree="torch.nn.functional.rrelu_",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    lower=helpers.floats(min_value=0, max_value=0.5, exclude_min=True),
    upper=helpers.floats(min_value=0.5, max_value=1.0, exclude_min=True),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_rrelu_(
    *,
    dtype_and_input,
    lower,
    upper,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        test_values=False,
        input=input[0],
        lower=lower,
        upper=upper,
    )


# scaled_dot_product_attention
@handle_frontend_test(
    fn_tree="torch.nn.functional.scaled_dot_product_attention",
    dtype_q_k_v_mask=_x_and_scaled_attention(
        dtypes=helpers.get_dtypes("float"),
    ),
    dropout_p=st.floats(min_value=0, max_value=0.99),
    is_causal=st.booleans(),
)
def test_torch_scaled_dot_product_attention(
    *,
    dtype_q_k_v_mask,
    dropout_p,
    is_causal,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    (dtype, query, key, value, mask) = dtype_q_k_v_mask
    is_causal = is_causal if mask is None else False
    helpers.test_frontend_function(
        input_dtypes=dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        test_values=dropout_p == 0.0,
        rtol=1e-05,
        atol=1e-05,
        query=query,
        key=key,
        value=value,
        attn_mask=mask,
        dropout_p=dropout_p,
        is_causal=is_causal,
    )


# selu
@handle_frontend_test(
    fn_tree="torch.nn.functional.selu",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    test_inplace=st.booleans(),
    test_with_out=st.just(False),
)
def test_torch_selu(
    *,
    dtype_and_input,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
    )


# sigmoid
@handle_frontend_test(
    fn_tree="torch.nn.functional.sigmoid",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
)
def test_torch_sigmoid(
    *,
    dtype_and_x,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        atol=1e-2,
        input=x[0],
    )


# silu
@handle_frontend_test(
    fn_tree="torch.nn.functional.silu",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_silu(
    *,
    dtype_and_input,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        rtol=1e-2,
        atol=1e-2,
        input=input[0],
    )


# softmax
@handle_frontend_test(
    fn_tree="torch.nn.functional.softmax",
    dtype_x_and_axis=helpers.dtype_values_axis(
        available_dtypes=helpers.get_dtypes("float"),
        min_num_dims=1,
        max_axes_size=1,
        force_int_axis=True,
        valid_axis=True,
    ),
    dtypes=helpers.get_dtypes("float", full=False),
)
def test_torch_softmax(
    *,
    dtype_x_and_axis,
    dtypes,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x, axis = dtype_x_and_axis
    ivy.set_backend(backend_fw)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
        dim=axis,
        _stacklevel=3,
        dtype=ivy.as_ivy_dtype(dtypes[0]),
    )
    ivy.previous_backend()


# softmin
@handle_frontend_test(
    fn_tree="torch.nn.functional.softmin",
    dtype_x_and_axis=helpers.dtype_values_axis(
        available_dtypes=helpers.get_dtypes("float"),
        min_num_dims=1,
        max_axes_size=1,
        force_int_axis=True,
        valid_axis=True,
    ),
    dtypes=helpers.get_dtypes("float", full=False),
)
def test_torch_softmin(
    *,
    dtype_x_and_axis,
    dtypes,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x, axis = dtype_x_and_axis
    ivy.set_backend(backend_fw)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
        dim=axis,
        dtype=ivy.as_ivy_dtype(dtypes[0]),
    )
    ivy.previous_backend()


# softplus
@handle_frontend_test(
    fn_tree="torch.nn.functional.softplus",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    beta=st.integers(min_value=1, max_value=20),
    threshold=st.integers(min_value=0, max_value=40),
    test_with_out=st.just(False),
)
def test_torch_softplus(
    *,
    dtype_and_x,
    beta,
    threshold,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=x[0],
        beta=beta,
        threshold=threshold,
    )


# softshrink
@handle_frontend_test(
    fn_tree="torch.nn.functional.softshrink",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    lambd=helpers.floats(min_value=0, max_value=1, exclude_min=True),
)
def test_torch_softshrink(
    *,
    dtype_and_input,
    lambd,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    _filter_dtypes(input_dtype)
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
        lambd=lambd,
    )


# softsign
@handle_frontend_test(
    fn_tree="torch.nn.functional.softsign",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("numeric"),
    ),
)
def test_torch_softsign(
    *,
    dtype_and_input,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
    )


# tanh
@handle_frontend_test(
    fn_tree="torch.nn.functional.tanh",
    dtype_and_x=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
)
def test_torch_tanh(
    *,
    dtype_and_x,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, x = dtype_and_x
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        atol=1e-2,
        input=x[0],
    )


# tanhshrink
@handle_frontend_test(
    fn_tree="torch.nn.functional.tanhshrink",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
)
def test_torch_tanhshrink(
    *,
    dtype_and_input,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
    )


# threshold
@handle_frontend_test(
    fn_tree="torch.nn.functional.threshold",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    threshold=helpers.floats(min_value=0.0, max_value=1.0),
    value=helpers.ints(min_value=5, max_value=20),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_threshold(
    *,
    dtype_and_input,
    threshold,
    value,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
        threshold=threshold,
        value=value,
    )


# threshold_
@handle_frontend_test(
    fn_tree="torch.nn.functional.threshold_",
    dtype_and_input=helpers.dtype_and_values(
        available_dtypes=helpers.get_dtypes("float"),
    ),
    threshold=helpers.floats(min_value=0.0, max_value=1.0),
    value=helpers.ints(min_value=5, max_value=20),
    test_with_out=st.just(False),
    test_inplace=st.booleans(),
)
def test_torch_threshold_(
    *,
    dtype_and_input,
    threshold,
    value,
    on_device,
    fn_tree,
    frontend,
    test_flags,
    backend_fw,
):
    input_dtype, input = dtype_and_input
    helpers.test_frontend_function(
        input_dtypes=input_dtype,
        backend_to_test=backend_fw,
        frontend=frontend,
        test_flags=test_flags,
        fn_tree=fn_tree,
        on_device=on_device,
        input=input[0],
        threshold=threshold,
        value=value,
    )
