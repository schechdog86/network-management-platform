#!/usr/bin/env python3
"""Model cache manager for AI worker nodes"""

import os
import sys
import json
import shutil
import hashlib
import time
from datetime import datetime, timedelta
import requests
from pathlib import Path
import argparse

class ModelCacheManager:
    def __init__(self):
        self.snap_common = os.environ.get('SNAP_COMMON', '.')
        self.cache_dir = os.path.join(self.snap_common, 'models')
        self.metadata_file = os.path.join(self.cache_dir, '.cache_metadata.json')
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Load metadata
        self.metadata = self.load_metadata()
        
        # Cache settings
        self.max_cache_size = 50 * 1024**3  # 50GB default
        self.cache_ttl_days = 30  # Keep models for 30 days
    
    def load_metadata(self):
        """Load cache metadata"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {'models': {}, 'last_cleanup': None}
    
    def save_metadata(self):
        """Save cache metadata"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def get_model_path(self, model_id):
        """Get local path for a model"""
        # Create a safe filename from model ID
        safe_name = model_id.replace('/', '_').replace('\\', '_')
        return os.path.join(self.cache_dir, safe_name)
    
    def calculate_checksum(self, filepath):
        """Calculate SHA256 checksum of a file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def download_model(self, model_url, model_id):
        """Download a model to cache"""
        model_path = self.get_model_path(model_id)
        
        print(f"Downloading model: {model_id}")
        print(f"From: {model_url}")
        print(f"To: {model_path}")
        
        # Create directory if needed
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        
        # Download with progress
        response = requests.get(model_url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        downloaded = 0
        with open(model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rProgress: {progress:.1f}%", end='', flush=True)
        
        print(f"\n✓ Download complete")
        
        # Calculate checksum
        checksum = self.calculate_checksum(model_path)
        
        # Update metadata
        self.metadata['models'][model_id] = {
            'path': model_path,
            'size': os.path.getsize(model_path),
            'checksum': checksum,
            'downloaded_at': datetime.utcnow().isoformat(),
            'last_accessed': datetime.utcnow().isoformat(),
            'access_count': 0
        }
        self.save_metadata()
        
        return model_path
    
    def get_model(self, model_id, model_url=None):
        """Get a model from cache or download if needed"""
        if model_id in self.metadata['models']:
            # Model exists in cache
            model_info = self.metadata['models'][model_id]
            model_path = model_info['path']
            
            if os.path.exists(model_path):
                # Update access time and count
                model_info['last_accessed'] = datetime.utcnow().isoformat()
                model_info['access_count'] += 1
                self.save_metadata()
                
                print(f"Model {model_id} found in cache")
                return model_path
            else:
                # Model file missing, remove from metadata
                del self.metadata['models'][model_id]
                self.save_metadata()
        
        # Model not in cache, download if URL provided
        if model_url:
            return self.download_model(model_url, model_id)
        else:
            raise ValueError(f"Model {model_id} not in cache and no URL provided")
    
    def list_models(self):
        """List all cached models"""
        print("=== Cached Models ===")
        
        total_size = 0
        for model_id, info in self.metadata['models'].items():
            size_gb = info['size'] / 1024**3
            total_size += info['size']
            
            last_accessed = datetime.fromisoformat(info['last_accessed'])
            days_old = (datetime.utcnow() - last_accessed).days
            
            print(f"\n{model_id}:")
            print(f"  Size: {size_gb:.2f} GB")
            print(f"  Downloaded: {info['downloaded_at']}")
            print(f"  Last accessed: {info['last_accessed']} ({days_old} days ago)")
            print(f"  Access count: {info['access_count']}")
            print(f"  Checksum: {info['checksum'][:16]}...")
        
        print(f"\nTotal cache size: {total_size / 1024**3:.2f} GB")
        print(f"Cache limit: {self.max_cache_size / 1024**3:.2f} GB")
    
    def cleanup_cache(self, force=False):
        """Clean up old or unused models"""
        print("=== Cache Cleanup ===")
        
        # Check if cleanup is needed
        last_cleanup = self.metadata.get('last_cleanup')
        if last_cleanup and not force:
            last_cleanup_date = datetime.fromisoformat(last_cleanup)
            if (datetime.utcnow() - last_cleanup_date).days < 1:
                print("Cache cleanup already run today")
                return
        
        removed_count = 0
        removed_size = 0
        
        # Remove models older than TTL
        for model_id, info in list(self.metadata['models'].items()):
            last_accessed = datetime.fromisoformat(info['last_accessed'])
            days_old = (datetime.utcnow() - last_accessed).days
            
            if days_old > self.cache_ttl_days:
                print(f"Removing {model_id} (not accessed for {days_old} days)")
                model_path = info['path']
                if os.path.exists(model_path):
                    os.remove(model_path)
                    removed_size += info['size']
                removed_count += 1
                del self.metadata['models'][model_id]
        
        # Check total cache size
        total_size = sum(info['size'] for info in self.metadata['models'].values())
        
        if total_size > self.max_cache_size:
            print(f"Cache size ({total_size / 1024**3:.2f} GB) exceeds limit ({self.max_cache_size / 1024**3:.2f} GB)")
            
            # Sort by last accessed time (oldest first)
            sorted_models = sorted(
                self.metadata['models'].items(),
                key=lambda x: x[1]['last_accessed']
            )
            
            # Remove oldest models until under limit
            for model_id, info in sorted_models:
                if total_size <= self.max_cache_size:
                    break
                
                print(f"Removing {model_id} to free space")
                model_path = info['path']
                if os.path.exists(model_path):
                    os.remove(model_path)
                    removed_size += info['size']
                    total_size -= info['size']
                removed_count += 1
                del self.metadata['models'][model_id]
        
        # Update last cleanup time
        self.metadata['last_cleanup'] = datetime.utcnow().isoformat()
        self.save_metadata()
        
        print(f"\nCleanup complete:")
        print(f"  Models removed: {removed_count}")
        print(f"  Space freed: {removed_size / 1024**3:.2f} GB")
    
    def verify_cache(self):
        """Verify integrity of cached models"""
        print("=== Cache Verification ===")
        
        corrupted = []
        missing = []
        
        for model_id, info in self.metadata['models'].items():
            model_path = info['path']
            
            if not os.path.exists(model_path):
                print(f"✗ {model_id}: File missing")
                missing.append(model_id)
                continue
            
            # Verify checksum
            print(f"Verifying {model_id}...", end='', flush=True)
            actual_checksum = self.calculate_checksum(model_path)
            
            if actual_checksum != info['checksum']:
                print(f" ✗ Checksum mismatch")
                corrupted.append(model_id)
            else:
                print(f" ✓ OK")
        
        # Remove corrupted/missing entries
        for model_id in corrupted + missing:
            del self.metadata['models'][model_id]
        
        if corrupted or missing:
            self.save_metadata()
            print(f"\nRemoved {len(corrupted + missing)} invalid entries from metadata")
        else:
            print("\n✓ All cached models verified successfully")
    
    def import_model(self, source_path, model_id):
        """Import a local model file into cache"""
        if not os.path.exists(source_path):
            print(f"Error: Source file not found: {source_path}")
            return
        
        model_path = self.get_model_path(model_id)
        
        print(f"Importing model: {model_id}")
        print(f"From: {source_path}")
        print(f"To: {model_path}")
        
        # Copy file
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        shutil.copy2(source_path, model_path)
        
        # Calculate checksum
        checksum = self.calculate_checksum(model_path)
        
        # Update metadata
        self.metadata['models'][model_id] = {
            'path': model_path,
            'size': os.path.getsize(model_path),
            'checksum': checksum,
            'downloaded_at': datetime.utcnow().isoformat(),
            'last_accessed': datetime.utcnow().isoformat(),
            'access_count': 0
        }
        self.save_metadata()
        
        print("✓ Model imported successfully")

def main():
    parser = argparse.ArgumentParser(description='Model Cache Manager')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # List command
    subparsers.add_parser('list', help='List cached models')
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get a model from cache')
    get_parser.add_argument('model_id', help='Model identifier')
    get_parser.add_argument('--url', help='URL to download from if not cached')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import a local model')
    import_parser.add_argument('source', help='Source file path')
    import_parser.add_argument('model_id', help='Model identifier')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old models')
    cleanup_parser.add_argument('--force', action='store_true', help='Force cleanup')
    
    # Verify command
    subparsers.add_parser('verify', help='Verify cache integrity')
    
    args = parser.parse_args()
    
    if not args.command:
        # Run as daemon
        manager = ModelCacheManager()
        print("Model cache manager started")
        while True:
            try:
                manager.cleanup_cache()
            except Exception as e:
                print(f"Error during cleanup: {e}")
            time.sleep(3600)  # Run cleanup every hour
    else:
        manager = ModelCacheManager()
        
        if args.command == 'list':
            manager.list_models()
        elif args.command == 'get':
            try:
                path = manager.get_model(args.model_id, args.url)
                print(f"Model available at: {path}")
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == 'import':
            manager.import_model(args.source, args.model_id)
        elif args.command == 'cleanup':
            manager.cleanup_cache(force=args.force)
        elif args.command == 'verify':
            manager.verify_cache()

if __name__ == '__main__':
    main()