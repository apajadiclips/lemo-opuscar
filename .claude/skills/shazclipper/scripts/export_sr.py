"""One-time: build Real-ESRGAN realesr-general-x4v3 (SRVGGNetCompact) from its .pth and export an ONNX model.
Runs in the Demucs venv (it has torch): $DEMUCS_PY export_sr.py <realesr-general-x4v3.pth> <out.onnx>
Weights: BSD-3-Clause (Real-ESRGAN, Xintao Wang et al.). Loaded with weights_only=True (no pickled code runs)."""
import sys, torch, torch.nn as nn, torch.nn.functional as F
class SRVGGNetCompact(nn.Module):
    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4):
        super().__init__(); self.upscale = upscale
        self.body = nn.ModuleList([nn.Conv2d(num_in_ch, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)])
        for _ in range(num_conv): self.body += [nn.Conv2d(num_feat, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        self.body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1)); self.upsampler = nn.PixelShuffle(upscale)
    def forward(self, x):
        out = x
        for m in self.body: out = m(out)
        return self.upsampler(out) + F.interpolate(x, scale_factor=self.upscale, mode="nearest")
sd = torch.load(sys.argv[1], map_location="cpu", weights_only=True)
sd = sd.get("params", sd.get("params_ema", sd))
net = SRVGGNetCompact(); net.load_state_dict(sd, strict=True); net.eval()
x = torch.rand(1, 3, 64, 64)
torch.onnx.export(net, x, sys.argv[2], input_names=["img"], output_names=["out"], opset_version=17,
                  dynamic_axes={"img": {2: "h", 3: "w"}, "out": {2: "H", 3: "W"}})
print("exported", sys.argv[2])
