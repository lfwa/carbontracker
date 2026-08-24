use crate::domain::providers::ProviderRegistry;

pub fn default_provider_registry() -> ProviderRegistry {
    let mut registry = ProviderRegistry::new();

    // Highest priority first. ProviderRegistry::resolve scans this list in
    // reverse and overwrites the chosen factory for every compatible match.
    #[cfg(target_os = "linux")]
    registry.register(RaplProviderFactory::new());

    #[cfg(target_os = "macos")]
    registry.register(PowermetricsProviderFactory::new());

    #[cfg(feature = "nvml")]
    registry.register(NvmlProviderFactory::new());

    registry.register(ElectricityMapsProviderFactory::new());
    registry.register(LocalizedAverageProviderFactory::new());
    registry.register(GlobalAverageProviderFactory::new());
    registry.register(StaticIntensityProviderFactory::new());

    registry
}
