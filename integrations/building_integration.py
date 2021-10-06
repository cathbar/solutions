from dataclasses import dataclass
from pathlib import Path
import pandas as pd
from model import integration
from integration_base import *
from solution import factory
import pdb

THISDIR = Path(__file__).parent
DATADIR = THISDIR/"data"/"building"

audit = start_audit("building")

building_solutions = {
    "Insulation (Residential Only)": "insulation",
    "Cool Roofs": "coolroofs",
    "Green Roofs": "greenroofs",
    "High Performance Glass-Residential Model": "residentialglass",
    "High Performance Glass- Commercial Model": "commercialglass",
    "Dynamic Glass (Commercial Only)": "smartglass",
    "Building Automation (Commercial Only)": "buildingautomation",
    "Smart Thermostats (Residential Only)": "smartthermostats",
    "Heat Pumps": "heatpumps",
    "District Heat": "districtheating",
    "Residential LED (Excludes Commercial LED)": "leds_residential",
    "Commercial LED (Excludes Household LED)": "leds_commercial",
    "Water Saving - Home (WaSH)": "waterefficiency",
    "Solar Hot Water (SHW)": "solarhotwater",
    "Biogas for Cooking": "biogas",
    "Clean Cookstoves":  "improvedcookstoves"
    }

# Load adoption data from solutions

@dataclass
class building_integration_state:
    # This data class holds global variables that are shared between steps.  Embedding it in a class
    # enables us to avoid having to declare 'global' anytime we want to change something.

    # In testmode, test data is loaded to check against calculations.
    # Turning testmode off reduces load time


    # All solutions that take part in the building integration
    # Key is the full name from excel sheet, value is the name in Python repo

    pds : str = 'pds1'
    cooking_global_tam : pd.DataFrame = pd.read_csv(DATADIR/"cooking_global_tam.csv", index_col="year", squeeze=False)
    floor_area_global_tam : pd.DataFrame = pd.read_csv(DATADIR/"floor_area_global_tam.csv", index_col="year", squeeze=False)
    households_global_tam : pd.DataFrame = pd.read_csv(DATADIR/"households_global_tam.csv", index_col="year", squeeze=False)
    lighting_global_tam : pd.DataFrame = pd.read_csv(DATADIR/"lighting_global_tam.csv", index_col="year", squeeze=False)
    roof_area_global_tam : pd.DataFrame = pd.read_csv(DATADIR/"roof_area_global_tam.csv", index_col="year", squeeze=False)
    space_cooling_global_tam : pd.DataFrame = pd.read_csv(DATADIR/"space_cooling_global_tam.csv", index_col="year", squeeze=False)
    space_heating_global_tam : pd.DataFrame = pd.read_csv(DATADIR/"space_heating_global_tam.csv", index_col="year", squeeze=False)
    water_heating_global_tam : pd.DataFrame = pd.read_csv(DATADIR/"water_heating_global_tam.csv", index_col="year", squeeze=False)

    adoption_dict = {}
    for key, value in building_solutions.items():
        adoption_dict[key] = load_solution_adoptions(value)[pds.upper()]
    adoption : pd.DataFrame = pd.DataFrame(data=adoption_dict)

    testmode = False
    # Load test data
    if testmode:
        adoption_test : pd.DataFrame = pd.read_csv(DATADIR/f"adoption_{pds}.csv", index_col="year", squeeze=False)
        fuel_avoided_test : pd.DataFrame = pd.read_csv(DATADIR/f"fuel_avoided_{pds}.csv", index_col="year", squeeze=False)
        net_grid_electricity_test : pd.DataFrame = pd.read_csv(DATADIR/f"net_grid_electricity_{pds}.csv", index_col="year", squeeze=False)

    test_adoption = False
    if test_adoption:
        adoption = adoption_test

    TWh_to_EJ : float = 3.6e-3
    EJ_to_TWh : float = 1/TWh_to_EJ
    TJ_to_EJ : float = 1e-6
    TJ_to_TWh : float = 1/3600

ds = building_integration_state()

def integrate():
    """Perform all steps of the integration together."""
    insulation_energy_saving = insulation_integration()
    coolroofs_energy_saving = cool_roofs_integration()
    greenroofs_energy_saving = green_roofs_integration()
    residentialglass_energy_saving = high_performance_glass_residential_integration()
    commercialglass_energy_saving = high_performance_glass_commercial_integration()
    space_heating_cooling_energy_saving = (
        insulation_energy_saving +
        coolroofs_energy_saving +
        greenroofs_energy_saving +
        residentialglass_energy_saving +
        commercialglass_energy_saving
        )
    return space_heating_cooling_energy_saving

def insulation_integration():
    """Step 1 in integration chain. Calculate the total energy saved and split
    saved energy into cooling and heating usage. Result does not affect other
    integration steps.
    
    Columns in Excel
    ----------------
    Adoption - Million m2 of Res Floor Area
        Copy pasted from the solution.
    Net Grid Electricity - TWh
        Copy pasted from the solution.
    Fuel Avoided - TJ
        Copy pasted from the solution.
    Total FINAL Energy Saved - EJ
        Calculated from the avoided fuel and the grid electricity used.
    Space Heating FINAL energy Saved - EJ
        Calculated from Total FINAL Energy Saved and several conversion factors.
    Space Cooling FINAL energy Saved - EJ
        Calculated from Total FINAL Energy Saved and several conversion factors.
    """
    insulation = factory.load_scenario('insulation')

    return insulation.total_energy_saving()

def cool_roofs_integration():
    """Step 2. Cool roofs calculation.
    
    Columns in Excel
    ----------------
    Adoption - Residential and Commercial roof area, m2
        Copy pasted from solution.
    Estimated Adoption Overlap with Insulation - Residential and Commercial roof area, m2
        Calculated based on Insulation adoption, Cool Roofs adoption, TAM Roof Area & TAM Floor Area.
    Electricity Consumption - TWh/m2 INTEGRATION PARAMETER
        This is a scalar paramter that is integrated. Integration is based on the pre-integration value,
        the adoption and the adoption overlap with insulation. 
    Thermal/Cooling Efficiency Factor - Percentage INTEGRATION PARAMETER
        This is a scalar parameter that is integrated.  Integration is based on the pre-integration value,
        the adoption and the adoption overlap with insulation
    INTEGRATION STEP
        Post-integration values from Electricity Consumption and Thermal/Cooling Efficiency Factor are inserted
        into the solution excel sheet. The resulting calculations of Net Grid Electricity Used and Fuel Avoided
        are copy pasted from the solution sheet to the integration sheet.
    Net Grid Electricity Used - TWh POST INTEGRATION
        Net grid electricity used after integration of Electricity consumption and Thermal/Cooling Efficiency
    Fuel Avoided - TJ POST INTEGRATION
        Fueld avoided after integration of Electricity consumption and Themrla/Cooling Efficiency
    Net EJ Reduction from Cool Roofs - EJ
        Calculated from Net Grid Electricity Used and Fuel Avoided.

    - Load scenario through the factory.
    - Get it's .ac as a dictionary
    - Change values to post-integration values
    - load scenario again through factory passing the changed dictionary as second argument

    Audit saves things in an audit log. 
    """
    coolroofs = factory.load_scenario('coolroofs', ds.pds.upper())
    insulation_overlap = (ds.adoption['Cool Roofs'] * ds.roof_area_global_tam['Roof Area - Residential - Case 1 - Average'] /
                                     ds.roof_area_global_tam['Roof Area - Total - Case 1 - Average'] * ds.adoption['Insulation (Residential Only)']  /
                                     ds.floor_area_global_tam['Residential - Average'])

    # Hardcoded into the integration excel sheet
    insulation_reduces_cool_roofs_heating_penalty = 0.75
    insulation_reduces_cool_roofs_electricity_impact = 0.5

    avg_reduction_fuel_impact = ((insulation_overlap.loc[2020:2050] / ds.adoption['Cool Roofs'].loc[2020:2050]).mean() * 
                                            insulation_reduces_cool_roofs_heating_penalty)
    avg_reduction_electricity_impact = ((insulation_overlap.loc[2020:2050] / ds.adoption['Cool Roofs'].loc[2020:2050]).mean() * 
                                        insulation_reduces_cool_roofs_electricity_impact)

    thermal_efficiency_factor = coolroofs.ac.soln_energy_efficiency_factor
    electricity_consumption_conventional = coolroofs.ac.conv_annual_energy_used
    electricity_consumption_pre_integration = coolroofs.ac.soln_annual_energy_used

    electricity_consumption_integrated = coolroofs.ac.conv_annual_energy_used

    thermal_efficiency_factor_integrated = thermal_efficiency_factor * (1-avg_reduction_fuel_impact)

    electricity_consumption_post_integration = (electricity_consumption_conventional -
        (electricity_consumption_conventional - electricity_consumption_pre_integration)*
        (1-avg_reduction_electricity_impact))

    """
    ac_integrated = coolroofs.ac.with_modifications(soln_annual_energy_used=electricity_consumption_post_integration,
                                                    soln_fuel_efficiency_factor=thermal_efficiency_factor_integrated)
    """

    # Integrate coolroofs
    # This also writes the new ac disk in solution directory
    coolroofs.update_ac(coolroofs.ac,
                        soln_annual_energy_used=electricity_consumption_post_integration,
                        soln_fuel_efficiency_factor=thermal_efficiency_factor_integrated)

    return coolroofs.total_energy_saving()

def green_roofs_integration():
    """Step 3. Green roofs calculation
    
    Columns in Excel
    ----------------
    Adoption - Residential and Commercial roof area, m2
        Copy pasted from solution.
    Estimated Adoption Overlap with Insulation - Residential and Commercial roof area, m2
        Calculated based on Insulation adoption, Cool Roofs adoption, TAM Roof Area & TAM Floor Area.
    Electricity Consumption - TWh/m2 INTEGRATION PARAMETER
        This is a scalar paramter that is integrated. Integration is based on the pre-integration value,
        the adoption and the adoption overlap with insulation. 
    Thermal/Cooling Efficiency Factor - Percentage INTEGRATION PARAMETER
        This is a scalar parameter that is integrated.  Integration is based on the pre-integration value,
        the adoption and the adoption overlap with insulation
    INTEGRATION STEP
        Post-integration values from Electricity Consumption and Thermal/Cooling Efficiency Factor are inserted
        into the solution excel sheet. The resulting calculations of Net Grid Electricity Used and Fuel Avoided
        are copy pasted from the solution sheet to the integration sheet.
    Net Grid Electricity Used - TWh POST INTEGRATION
        Net grid electricity used after integration of Electricity consumption and Thermal/Cooling Efficiency
    Fuel Avoided - TJ POST INTEGRATION
        Fueld avoided after integration of Electricity consumption and Themrla/Cooling Efficiency
    Net EJ Reduction from Cool Roofs - EJ
        Calculated from Net Grid Electricity Used and Fuel Avoided.

    - Load scenario through the factory.
    - Get it's .ac as a dictionary
    - Change values to post-integration values
    - load scenario again through factory passing the changed dictionary as second argument

    Audit saves things in an audit log. 
    """

    greenroofs = factory.load_scenario('greenroofs', ds.pds.upper())
    insulation_overlap = (ds.adoption['Green Roofs'] * ds.roof_area_global_tam['Roof Area - Residential - Case 1 - Average'] /
                                     ds.roof_area_global_tam['Roof Area - Total - Case 1 - Average'] * ds.adoption['Insulation (Residential Only)']  /
                                     ds.floor_area_global_tam['Residential - Average'])

    # Hardcoded into the integration excel sheet
    insulation_reduces_green_roofs_heating_penalty = 0.5
    insulation_reduces_green_roofs_electricity_impact = 0.5

    avg_reduction_fuel_impact = ((insulation_overlap.loc[2020:2050] / ds.adoption['Green Roofs'].loc[2020:2050]).mean() * 
                                            insulation_reduces_green_roofs_heating_penalty)
    avg_reduction_electricity_impact = ((insulation_overlap.loc[2020:2050] / ds.adoption['Green Roofs'].loc[2020:2050]).mean() * 
                                        insulation_reduces_green_roofs_electricity_impact)

    # TODO These are hardcoded for now but should be taken from solution.ac at some point
    # Currently the numbers we have in Python are clearly outdated though
    thermal_efficiency_factor = greenroofs.ac.soln_energy_efficiency_factor
    electricity_consumption_conventional = greenroofs.ac.conv_annual_energy_used
    electricity_consumption_pre_integration = greenroofs.ac.soln_annual_energy_used

    electricity_consumption_integrated = greenroofs.ac.conv_annual_energy_used

    thermal_efficiency_factor_integrated = thermal_efficiency_factor * (1-avg_reduction_fuel_impact)

    electricity_consumption_post_integration = (electricity_consumption_conventional -
        (electricity_consumption_conventional - electricity_consumption_pre_integration)*
        (1-avg_reduction_electricity_impact))

    # Integrate greenroofs
    greenroofs.update_ac(greenroofs.ac,
                        soln_annual_energy_used=electricity_consumption_post_integration,
                        soln_fuel_efficiency_factor=thermal_efficiency_factor_integrated)


    return greenroofs.total_energy_saving()

def high_performance_glass_residential_integration():
    """Step 4. Combines calculation for residential and commercial high performance
    glass. """
    residentialglass = factory.load_scenario('residentialglass', ds.pds.upper())
    
    insulation_overlap = ds.adoption['Insulation (Residential Only)'] / ds.floor_area_global_tam['Residential - Average'] * ds.adoption["High Performance Glass-Residential Model"] 

    insulation_reduces_glass_electricity_impact = 0.5
    insulation_reduces_glass_fuel_impact = 0.5

    average_reduction_electricity_efficiency = ((insulation_overlap.loc[2020:2050] / ds.adoption["High Performance Glass-Residential Model"].loc[2020:2050]).mean() * 
                                        insulation_reduces_glass_electricity_impact)

    average_reduction_fuel_efficiency = ((insulation_overlap.loc[2020:2050] / ds.adoption["High Performance Glass-Residential Model"].loc[2020:2050]).mean() * 
                                        insulation_reduces_glass_fuel_impact)

    fuel_inputs_conv = residentialglass.ac.conv_fuel_consumed_per_funit
    fuel_inputs_soln_efficiency = residentialglass.ac.soln_fuel_efficiency_factor
    thermal_efficiency_factor = residentialglass.ac.soln_energy_efficiency_factor
    electricity_consumption_conventional = residentialglass.ac.conv_annual_energy_used
    electricity_consumption_pre_integration = residentialglass.ac.soln_annual_energy_used

    # goes to total_energy_used_per_functional_unit solution
    electricity_inputs_integrated = (electricity_consumption_conventional -
        (electricity_consumption_conventional - electricity_consumption_pre_integration)*
        (1-average_reduction_electricity_efficiency))

    # goes to fuel_inputs_soln_efficiency
    fuel_inputs_integrated = fuel_inputs_soln_efficiency * (1 - average_reduction_fuel_efficiency)

    # pdb.set_trace()

    residentialglass.update_ac(residentialglass.ac,
                    soln_annual_energy_used=electricity_inputs_integrated,
                    soln_fuel_efficiency_factor=fuel_inputs_integrated)

    return residentialglass.total_energy_saving()

def high_performance_glass_commercial_integration():
    """No integration needed because insulation is defined only for residential buildings."""
    smartglass = factory.load_scenario('smartglass', ds.pds.upper())
    return smartglass.total_energy_saving()

def led_integration():
    """Step 5. LED integration."""
    pass

def dynamic_glass_integration():
    """Step 6. Dynamic glass integration. Depends on both high performance glass
    and LED. Commercial only."""
    commercialglass = factory.load_scenario('commercialglass', ds.pds.upper())

def building_automation_integration():
    """Step 7. Building automation. Depends on dynamic glass."""

    buildingautomation = factory.load_scenario('buildingautomation', ds.pds.upper())

    numstories_comm = 1.58

    possible_overlap = ((ds.adoption['Cool Roofs'] + ds.adoption['Green Roofs']) / 1e6 * 
        ds.roof_area_global_tam['Roof Area - Residential - Case 1 - Average'] / ds.roof_area_global_tam['Roof Area - Residential - Case 1 - Average'] * numstories_comm
        )
    columns_max = pd.DataFrame({'col1':possible_overlap, 
                                'col2': ds.adoption['High Performance Glass- Commercial Model'],
                                'col3': ds.adoption['Insulation (Residential Only)']}).max(axis=1)
    adoption_overlap = columns_max / ds.floor_area_global_tam['Residential - Average'] * ds.adoption['Building Automation (Commercial Only)']

    roof_glass_electricity_impact = 0.5
    roof_glass_fuel_impact = 0.5

    average_change_heating_electricity_efficiency = (
        (adoption_overlap.loc[2020:2050] / ds.adoption['Building Automation (Commercial Only)'].loc[2020:2050]).mean() * 
        roof_glass_electricity_impact
        )

    average_change_fuel_efficiency = (
        (adoption_overlap.loc[2020:2050] / ds.adoption['Building Automation (Commercial Only)'].loc[2020:2050]).mean() * 
        roof_glass_fuel_impact)

    fuel_efficiency_factor = buildingautomation.ac.soln_fuel_efficiency_factor
    electrical_efficiency_factor = buildingautomation.ac.soln_energy_efficiency_factor

    # TODO Locate these in the sollutions!
    electricity_end_use_shares_heating_cooling = 0.296
    electricity_end_use_shares_lighting = 0.236
    lighting_energy_impact = 0.326

    electrical_efficiency_factor_integrated = (
        electrical_efficiency_factor * ((1 - electricity_end_use_shares_heating_cooling - electricity_end_use_shares_lighting)) + 
        electricity_end_use_shares_heating_cooling * (1 - average_change_heating_electricity_efficiency) + 
        electricity_end_use_shares_lighting * (1 - lighting_energy_impact)
    )

    fuel_efficiency_factor_integrated = fuel_efficiency_factor * (1 - average_change_fuel_efficiency)

    buildingautomation.update_ac(buildingautomation.ac,
                soln_fuel_efficiency_factor=fuel_efficiency_factor_integrated,
                soln_energy_efficiency_factor=electrical_efficiency_factor_integrated)

    pdb.set_trace()

    # TODO take care of the sign change in net_impact!
    return buildingautomation.total_energy_saving()

def smart_thermostat_integration():
    """Step 8. Smart thermostat. Depends on building automation"""
    pass

def heat_pumps_integration():
    """Step 9. Heat pumpts. Depends on smart thermostat."""
    pass

def district_heating_integration():
    """Step 10. District heating. Depends on heat pumps."""
    pass

def cooking_biogas_integration():
    """Step 11. Cooking biogas. No upstream dependency."""
    pass

def clean_stoves_integration():
    """Step 12. Clean stoves. Depends on cooking biogas."""
    pass

def low_flow_fixtures_integration():
    """Step 13. Lo-flow fixtures. No upstream dependency."""
    pass

def solar_hw_integration():
    """Step 14. Solar HW. Depends on low flow fixtures."""
