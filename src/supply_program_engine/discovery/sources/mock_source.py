from typing import List
from ..models import DiscoveredCompany


def discover() -> List[DiscoveredCompany]:
    return [
        DiscoveredCompany(
            company_name="Lone Star Industrial Panels",
            website="https://lonestarpanels-example.com",
            location="Texas",
            source="mock_directory",
            discovered_via="industrial distributor",
            external_id="mock-1",
            source_query="industrial distributor",
            source_region="Texas",
            source_confidence=0.95,
        ),
        DiscoveredCompany(
            company_name="Florida Formwork Solutions",
            website="https://floridaformwork-example.com",
            location="Florida",
            source="mock_directory",
            discovered_via="formwork contractor",
            external_id="mock-2",
            source_query="formwork contractor",
            source_region="Florida",
            source_confidence=0.95,
        ),
    ]
