package coil.compose

import androidx.compose.foundation.Image
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import coil3.compose.rememberAsyncImagePainter

/** Compatibility shim for the existing UI while the app uses Coil 3. */
@Composable
fun AsyncImage(
    model: Any?,
    contentDescription: String?,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Fit
) {
    Image(
        painter = rememberAsyncImagePainter(model),
        contentDescription = contentDescription,
        modifier = modifier,
        contentScale = contentScale
    )
}
