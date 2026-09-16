"""Демонстрационный набор скважин для быстрой проверки программы."""

from __future__ import annotations

from .models import Well


def make_sample_wells() -> list[Well]:
    return [
        Well(
            id="101", name="Скв. 101", formation="БС10", status="active",
            qo=8.5, ql=10.0, watercut=15.0,
            p_res=210, p_res_initial=250, p_wf=90,
            skin=8.5, perm=6.0, thickness_total=12.0, thickness_perforated=12.0,
            reserves_remaining=45.0, depletion=35.0,
            pump_capacity=25.0, months_since_last_gtm=24,
        ),
        Well(
            id="102", name="Скв. 102", formation="БС10", status="active",
            qo=4.2, ql=40.0, watercut=89.0,
            p_res=195, p_res_initial=250, p_wf=85,
            skin=1.5, perm=25.0, thickness_total=10.0, thickness_perforated=10.0,
            reserves_remaining=18.0, depletion=72.0,
            pump_capacity=45.0, months_since_last_gtm=36,
        ),
        Well(
            id="103", name="Скв. 103", formation="АС4", status="active",
            qo=2.0, ql=2.3, watercut=98.5,
            p_res=180, p_res_initial=240, p_wf=80,
            skin=2.0, perm=18.0, thickness_total=16.0, thickness_perforated=8.0,
            reserves_remaining=32.0, depletion=55.0,
            pump_capacity=15.0, months_since_last_gtm=48,
        ),
        Well(
            id="104", name="Скв. 104", formation="АС4", status="idle",
            qo=0.0, ql=0.0, watercut=0.0,
            p_res=205, p_res_initial=240, p_wf=0,
            skin=0.0, perm=20.0, thickness_total=9.0, thickness_perforated=9.0,
            reserves_remaining=22.0, depletion=40.0,
            idle_days=180, last_active_qo=6.0, months_since_last_gtm=999,
        ),
        Well(
            id="105", name="Скв. 105", formation="БС10", status="active",
            qo=12.0, ql=13.0, watercut=8.0,
            p_res=230, p_res_initial=250, p_wf=110,
            skin=1.0, perm=45.0, thickness_total=14.0, thickness_perforated=14.0,
            reserves_remaining=60.0, depletion=20.0,
            pump_capacity=50.0, months_since_last_gtm=3,
        ),
        Well(
            id="106", name="Скв. 106", formation="ЮС2", status="active",
            qo=3.5, ql=4.0, watercut=12.0,
            p_res=200, p_res_initial=230, p_wf=95,
            skin=4.5, perm=4.5, thickness_total=8.0, thickness_perforated=8.0,
            reserves_remaining=25.0, depletion=30.0,
            pump_capacity=30.0, months_since_last_gtm=18,
        ),
        Well(
            id="107", name="Скв. 107", formation="ЮС2", status="active",
            qo=6.0, ql=42.0, watercut=86.0,
            p_res=190, p_res_initial=235, p_wf=88,
            skin=2.5, perm=30.0, thickness_total=11.0, thickness_perforated=11.0,
            reserves_remaining=40.0, depletion=48.0,
            pump_capacity=45.0, months_since_last_gtm=15,
        ),
        Well(
            id="108", name="Скв. 108", formation="АС4", status="active",
            qo=5.0, ql=5.5, watercut=9.0,
            p_res=215, p_res_initial=245, p_wf=100,
            skin=1.2, perm=22.0, thickness_total=18.0, thickness_perforated=11.0,
            reserves_remaining=38.0, depletion=25.0,
            pump_capacity=20.0, months_since_last_gtm=9,
        ),
        Well(
            id="109", name="Скв. 109", formation="БС10", status="idle",
            qo=0.0, ql=0.0, watercut=0.0,
            p_res=175, p_res_initial=245, p_wf=0,
            skin=0.0, perm=10.0, thickness_total=10.0, thickness_perforated=10.0,
            reserves_remaining=1.0, depletion=92.0,
            idle_days=900, last_active_qo=2.0, months_since_last_gtm=999,
        ),
        Well(
            id="110", name="Скв. 110", formation="ЮС2", status="active",
            qo=9.0, ql=9.5, watercut=5.0,
            p_res=225, p_res_initial=245, p_wf=105,
            skin=0.5, perm=60.0, thickness_total=13.0, thickness_perforated=13.0,
            reserves_remaining=55.0, depletion=15.0,
            pump_capacity=10.0, months_since_last_gtm=4,
        ),
    ]
