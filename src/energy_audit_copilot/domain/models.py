"""Typed placeholders for core audit entities."""

from pydantic import BaseModel


class Building(BaseModel):
    building_id: str
    building_name: str


class UtilityBill(BaseModel):
    bill_id: str
    building_id: str
    meter_type: str


class EquipmentItem(BaseModel):
    equipment_id: str
    building_id: str
    system_type: str


class AuditMeasure(BaseModel):
    measure_id: str
    building_id: str
    measure_name: str
