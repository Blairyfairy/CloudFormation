#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/.build"
SHARED="$ROOT/backend/shared"
rm -rf "$BUILD"
mkdir -p "$BUILD"

package_lambda () {
  local name="$1"
  mkdir -p "$BUILD/$name"
  cp "$ROOT/backend/lambda/$name/app.py" "$BUILD/$name/app.py"
  cp "$SHARED/"*.py "$BUILD/$name/"
  (cd "$BUILD/$name" && zip -qr "$BUILD/$name.zip" .)
  echo "Packaged $name.zip"
}

package_lambda create_order
package_lambda capture_order
package_lambda create_upload_url
package_lambda start_processing
package_lambda get_job
package_lambda process_media

echo "All packages created in $BUILD"
