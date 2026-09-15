from switching_loss_engine import CalculationRequest, OperatingPointInput, ParasiticsInput, calculate


request = CalculationRequest(
    device_id="C2M0025120D",
    model="M3",
    operating_point=OperatingPointInput(800, 40, 125, 5, 5),
    parasitics=ParasiticsInput(lg_H=5e-9, ls_H=5e-9, lloop_H=20e-9),
    return_waveforms=False,
)
result = calculate(request)
print(result.as_dict(include_waveforms=False))

