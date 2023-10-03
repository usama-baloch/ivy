import ivy
from ivy.functional.frontends.torch.func_wrapper import to_ivy_arrays_and_back
from ivy.func_wrapper import with_supported_dtypes


@to_ivy_arrays_and_back
def bartlett_window(
    window_length,
    periodic=True,
    *,
    dtype=None,
    layout=None,
    device=None,
    requires_grad=False
):
    # this implementation is based on scipy.signal.windows.bartlett
    # https://github.com/scipy/scipy/blob/v1.11.2/scipy/signal/windows/_windows.py#L625-L721
    if int(window_length) != window_length or window_length < 0:
        raise ValueError("Window length must be a non-negative integer")
    elif window_length == 1:
        return ivy.ones(window_length)
    else:
        N = window_length + 1 if periodic else window_length

        res = ivy.arange(0, N, dtype=dtype)
        res = ivy.where(
            ivy.less_equal(res, (N - 1) / 2.0),
            2.0 * res / (N - 1),
            2.0 - 2.0 * res / (N - 1),
        )

        return res[:-1] if periodic else res


@to_ivy_arrays_and_back
@with_supported_dtypes({"2.51.0 and below": ("float32", "float64")}, "torch")
def blackman_window(
    window_length,
    periodic=True,
    *,
    dtype=None,
    layout=None,
    device=None,
    requires_grad=False
):
    return ivy.blackman_window(window_length, periodic=periodic, dtype=dtype)
