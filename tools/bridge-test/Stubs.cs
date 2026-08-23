// The only KSP type the transport files touch. Field-for-field with KSP's, so AxeJson.Vec
// compiles unchanged and the serialised shape under test is the real one.
public struct Vector3d
{
    public double x, y, z;
    public Vector3d(double x, double y, double z) { this.x = x; this.y = y; this.z = z; }
}
