using ArcGIS.Desktop.Framework;
using ArcGIS.Desktop.Framework.Contracts;

namespace GCN_HSI_AddinPro
{
    internal class Module1 : Module
    {
        private static Module1 _this = null;

        public static Module1 Current => _this ??= (Module1)FrameworkApplication.FindModule("GCN_HSI_Module");

        protected override bool CanUnload()
        {
            return true;
        }
    }
}
