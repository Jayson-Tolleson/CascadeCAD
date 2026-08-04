from app.core.config import get_settings
from app.layers.contracts import LayerContract
from app.providers.gfs_ncss import get_gfs_provider
from app.providers.rtofs_ncep import get_rtofs_provider
from app.spatial.postgis_optional import postgis_status

BASE_BUDGET = {
    'global': {'clouds': 16, 'rain': 20, 'bait': 12, 'boats': 6, 'shark-intel': 10, 'lightning': 12, 'inland-water': 20, 'reports': 12},
    'regional': {'clouds': 32, 'rain': 40, 'bait': 24, 'boats': 12, 'shark-intel': 24, 'lightning': 24, 'inland-water': 60, 'reports': 24},
    'local': {'clouds': 56, 'rain': 72, 'bait': 40, 'boats': 24, 'shark-intel': 48, 'lightning': 50, 'inland-water': 120, 'reports': 40},
}


def layer_contracts() -> list[LayerContract]:
    settings = get_settings()
    return [
        # Locations are intentionally first: CSV green orbs should load before heavy overlays
        # and the pill must be leftmost in both API contracts and frontend UI.
        LayerContract(id='locations', label='Locations', kind='spatial_points', source='zippy csv/postgis location reports', depends_on=['viewport-spatial.locations'], stream_events=['locations.patch'], renderer='LocationOrbLayer', budget={k: v['reports'] for k, v in BASE_BUDGET.items()}),
        LayerContract(id='clouds', label='Clouds', kind='field', source='gfs_ncss_live_cloud_features + postgis.cloud_render_features', depends_on=['cloud.features.patch', 'atmosphere.field.patch'], stream_events=['cloud.features.patch', 'atmosphere.field.patch'], renderer='Google3DCloudParticlePolygons', budget={k: v['clouds'] for k, v in BASE_BUDGET.items()}),
        LayerContract(id='rain', label='Rain', kind='field', source='gfs_ncss_atmosphere.rain_rate + cloud_family_height_channels', depends_on=['atmosphere.field.patch'], stream_events=['atmosphere.field.patch'], renderer='Google3DRainColoredSphereColumns', budget={k: v['rain'] for k, v in BASE_BUDGET.items()}),
        # No standalone Ocean pill: the ocean field remains the data source under Bait, Boats, and Shark Intel.
        LayerContract(id='bait', label='Bait', kind='scalar_field', source='ocean_truth.bait_score + rtofs_ncep_ocean.currents_sst', depends_on=['ocean.field.patch'], stream_events=['ocean.field.patch'], renderer='BaitFieldLayer', budget={k: v['bait'] for k, v in BASE_BUDGET.items()}, todo=['Future chlorophyll boost', 'Future depth-aware bait scoring']),
        LayerContract(id='boats', label='Boats', kind='entity', source='viewport+spatial_water+ocean_current', depends_on=['viewport-spatial', 'ocean.field.patch'], stream_events=['boats.patch'], renderer='BoatLayer', budget={k: v['boats'] for k, v in BASE_BUDGET.items()}, todo=['Replace mock generator with AIS/user vessel sources later']),
        LayerContract(id='shark-intel', label='Shark Intel', kind='event', source='csv shark mentions + ocean_truth bait/current/temp', depends_on=['viewport-spatial.locations', 'ocean.field.patch'], stream_events=['locations.patch', 'ocean.field.patch'], renderer='SharkIntelLayer', budget={k: v['shark-intel'] for k, v in BASE_BUDGET.items()}, todo=['Add external shark telemetry later']),
        LayerContract(id='inland-water', label='Inland Water', kind='spatial', source='usgs/postgis waterbodies', depends_on=['viewport-spatial.waterbodies'], stream_events=[], renderer='InlandWaterLayer', budget={k: v['inland-water'] for k, v in BASE_BUDGET.items()}, todo=['Live lake temperature later']),
        LayerContract(id='lightning', label='Lightning', kind='event', enabled=settings.lightning_enabled, source=f'{settings.lightning_provider}_lightning', depends_on=['lightning.flash'], stream_events=['lightning.flash'], renderer='LightningLayer', budget={k: v['lightning'] for k, v in BASE_BUDGET.items()}, degraded=not settings.lightning_enabled, todo=['Future GLM provider']),
    ]


def layer_status() -> dict:
    return {
        'ok': True,
        'contract_version': 'lftr.layers.v1',
        'layers': [contract.model_dump(mode='json') for contract in layer_contracts()],
        'providers': {'gfs': get_gfs_provider().status().model_dump(mode='json'), 'rtofs': get_rtofs_provider().status().model_dump(mode='json')},
        'spatial': {'postgis': postgis_status()},
        'renderer_expectations': {'flow': 'snapshot -> stream -> field store -> target state -> animation loop -> morphing object pools', 'no_full_redraw': True},
    }
