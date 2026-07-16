// Enhanced icon registry with error handling and lazy loading
import { BrandIcon } from './brandIcons';

export interface IconMetadata extends BrandIcon {
  loaded: boolean;
  error?: string;
  fallbackUrl?: string;
}

export class IconRegistry {
  private static instance: IconRegistry;
  private icons: Map<string, IconMetadata> = new Map();
  private loadingPromises: Map<string, Promise<void>> = new Map();

  static getInstance(): IconRegistry {
    if (!IconRegistry.instance) {
      IconRegistry.instance = new IconRegistry();
    }
    return IconRegistry.instance;
  }

  async loadIcon(key: string): Promise<IconMetadata> {
    if (this.icons.has(key)) {
      return this.icons.get(key)!;
    }

    if (this.loadingPromises.has(key)) {
      await this.loadingPromises.get(key);
      return this.icons.get(key)!;
    }

    const promise = this.loadSingleIcon(key);
    this.loadingPromises.set(key, promise);

    try {
      await promise;
    } finally {
      this.loadingPromises.delete(key);
    }

    return this.icons.get(key)!;
  }

  private async loadSingleIcon(key: string): Promise<void> {
    const source = BRAND_ICONS[key];
    if (!source) {
      const metadata: IconMetadata = {
        title: `Missing icon: ${key}`,
        hex: '64748b',
        path: 'M0 0h24v24H0z',
        loaded: true,
        error: 'Icon not found in registry',
      };
      this.icons.set(key, metadata);
      return;
    }

    try {
      // Preload the image to check if icon loads successfully
      const img = new Image();
      const svgData = `data:image/svg+xml;base64,${btoa(source.path)}`;
      
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => reject();
        img.src = svgData;
      });

      const metadata: IconMetadata = {
        ...source,
        loaded: true,
        error: undefined,
      };
      this.icons.set(key, metadata);
    } catch (error) {
      const metadata: IconMetadata = {
        ...source,
        loaded: false,
        error: error instanceof Error ? error.message : 'Failed to load icon',
        fallbackUrl: 'https://cdn.simpleicons.org/' + key, // For third-party icons
      };
      this.icons.set(key, metadata);
    }
  }

  getIcon(key: string): IconMetadata | undefined {
    return this.icons.get(key);
  }

  async ensureLoaded(key: string): Promise<boolean> {
    const icon = this.icons.get(key);
    if (icon?.loaded) return true;
    if (icon?.loading) return false; // Still loading

    try {
      await this.loadIcon(key);
      return true;
    } catch {
      return false;
    }
  }

  async preloadBatch(keys: string[]): Promise<Map<string, boolean>> {
    const results = new Map<string, boolean>();
    await Promise.all(
      keys.map(async (key) => {
        try {
          await this.loadIcon(key);
          results.set(key, true);
        } catch {
          results.set(key, false);
        }
      })
    );
    return results;
  }
}

export const iconRegistry = IconRegistry.getInstance();

export function useIconRegistry() {
  // React hook for icon registry state
  const [registry] = useState(IconRegistry.getInstance());
  const [state, setState] = useState<Map<string, IconMetadata>>(
    new Map(Array.from(registry.getIcons?.() || []))
  );

  useEffect(() => {
    const updateState = () => {
      setState(new Map(registry.getIcons?.() || []));
    };

    // Subscribe to registry changes
    registry.onChange?.(updateState);
    return () => registry.offChange?.(updateState);
  }, [registry]);

  return {
    registry,
    state,
    loadIcon: registry.loadIcon.bind(registry),
    getIcon: registry.getIcon.bind(registry),
  };
}
