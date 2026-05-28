using ArcGIS.Desktop.Core.Geoprocessing;
using Button = ArcGIS.Desktop.Framework.Contracts.Button;
using System.IO;
using System.Reflection;

namespace GCN_HSI_AddinPro
{
    internal class GCNHabitatSuitabilityButton : Button
    {
        protected override void OnClick()
        {
            string installDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string toolboxPath = Path.Combine(installDir, "GCNHabitatSuitability.pyt");
            _ = Geoprocessing.OpenToolDialogAsync($"{toolboxPath}\\GCNHabitatSuitability");
        }
    }
}
