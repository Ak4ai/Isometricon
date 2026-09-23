"""Módulo nativo de vestuário e customização 3D do Isometricon."""

def get_wear_engine(*args, **kwargs):
    from .wear_engine import RobloxWearEngine
    return RobloxWearEngine(*args, **kwargs)

def wear_asset(asset_id, output_obj=None):
    from .wear_engine import wear_asset as _wear
    return _wear(asset_id, output_obj=output_obj)

__all__ = ["get_wear_engine", "wear_asset"]
