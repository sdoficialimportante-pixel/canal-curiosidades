# Canal de curiosidades: 1 Short al día, 100 % gratis

Cada día GitHub ejecuta `generate_short.py`, que:
1. Elige un tema nuevo (con Gemini gratis, o del banco `facts_bank.json`).
2. Genera la voz en español (edge-tts, gratis).
3. Descarga vídeos de fondo verticales de Pexels (gratis).
4. Monta el vídeo con subtítulos (ffmpeg, gratis).
5. Lo sube a tu canal de YouTube.

Configuración única: unos 30 minutos.

---

## Paso 1. Subir el proyecto a GitHub

1. Crea una cuenta en https://github.com (gratis).
2. Pulsa **New repository**. Nómbralo `canal-curiosidades` y márcalo como **Public** (en repositorios públicos GitHub Actions es gratis sin límite).
3. Pulsa **uploading an existing file** y arrastra TODO el contenido de esta carpeta, incluida la carpeta oculta `.github`. Si tu sistema no te deja ver carpetas ocultas, usa el botón **Add file → Create new file** y crea el archivo `.github/workflows/short-diario.yml` pegando su contenido.
4. Pulsa **Commit changes**.

## Paso 2. Clave de Pexels (vídeos de fondo)

1. Entra en https://www.pexels.com/api/ y crea una cuenta gratuita.
2. Pide tu clave de API y cópiala.

## Paso 3. Clave de Gemini (opcional)

Sirve para que los guiones no se acaben nunca. Sin ella, se usan los 10 temas de `facts_bank.json`, uno por día, y luego se acaban.

1. Entra en https://aistudio.google.com/apikey con tu cuenta de Google.
2. Pulsa **Create API key** y cópiala.
3. Comprueba que el plan gratuito sigue disponible. Si el modelo `gemini-2.5-flash` ya no existe, añade un secreto `GEMINI_MODEL` con el nombre del modelo actual.

## Paso 4. Permiso para subir a YouTube

1. Entra en https://console.cloud.google.com y crea un proyecto nuevo.
2. Menú **APIs y servicios → Biblioteca**: busca **YouTube Data API v3** y pulsa **Habilitar**.
3. **APIs y servicios → Pantalla de consentimiento de OAuth**: tipo **Externo**, pon el nombre que quieras y tu correo. En **Usuarios de prueba** añade tu propio correo.
4. **IMPORTANTE:** al terminar, pulsa **Publicar la aplicación** (pasar de "Prueba" a "En producción"). Si la dejas en prueba, el permiso caduca a los 7 días y el flujo dejará de funcionar. Saldrá un aviso de "app no verificada": es normal, es tu propia app.
5. **Credenciales → Crear credenciales → ID de cliente de OAuth**. Tipo **Aplicación web**. En **URI de redireccionamiento autorizados** añade exactamente:
   `https://developers.google.com/oauthplayground`
6. Copia el **ID de cliente** y el **Secreto de cliente**.
7. Entra en https://developers.google.com/oauthplayground
   - Pulsa el engranaje (arriba a la derecha), marca **Use your own OAuth credentials** y pega tu ID y secreto.
   - En el cuadro de la izquierda escribe el permiso `https://www.googleapis.com/auth/youtube.upload` y pulsa **Authorize APIs**.
   - Inicia sesión con la cuenta dueña del canal y acepta (pasa por el aviso de app no verificada).
   - Pulsa **Exchange authorization code for tokens** y copia el **Refresh token**.

## Paso 5. Guardar las claves en GitHub

En tu repositorio: **Settings → Secrets and variables → Actions → New repository secret**. Crea estos secretos, con estos nombres exactos:

| Nombre | Valor |
|---|---|
| `PEXELS_API_KEY` | clave de Pexels |
| `GEMINI_API_KEY` | clave de Gemini (opcional) |
| `YT_CLIENT_ID` | ID de cliente de Google |
| `YT_CLIENT_SECRET` | secreto de cliente de Google |
| `YT_REFRESH_TOKEN` | el refresh token |

## Paso 6. Probar sin subir nada

1. Pestaña **Actions** de tu repositorio. Si te pide activarlas, acepta.
2. Elige **Short diario → Run workflow**, escribe `1` en la casilla y ejecuta.
3. Al terminar (unos 3 a 5 minutos), abre la ejecución y descarga el vídeo desde **Artifacts → short-de-prueba**. Mira que te guste el resultado.

## Paso 7. Activar la subida diaria

Ejecuta de nuevo **Run workflow** con el valor `0`. Debería aparecer el vídeo en tu canal. A partir de entonces se ejecuta solo todos los días sobre las 09:00 o 10:00 (hora de España).

---

## Cosas a tener en cuenta

- **Privados al principio:** hasta que Google verifique tu proyecto, YouTube puede dejar los vídeos subidos por API como privados. Si pasa, hay que solicitar la auditoría de la API en Google Cloud, o publicarlos tú a mano desde YouTube Studio.
- **Para probar en privado:** crea un secreto o variable `PRIVACY_STATUS` con el valor `private`.
- **Monetización:** YouTube puede limitar el alcance de canales con muchos vídeos repetitivos y de producción masiva. Revisa de vez en cuando los guiones, y cambia las palabras clave de fondo para dar variedad.
- **Si se detiene:** en la pestaña Actions puedes reactivar el flujo. GitHub desactiva las tareas programadas de repositorios sin actividad durante mucho tiempo.
- **Voz:** cambia `TTS_VOICE` por otra voz (por ejemplo `es-ES-ElviraNeural`) si prefieres una voz femenina.
- **Límite de la voz gratuita:** edge-tts usa un servicio de Microsoft sin garantía oficial. Si algún día deja de funcionar, habrá que cambiar de voz o de librería.
