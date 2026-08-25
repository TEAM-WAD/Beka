import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';

void main() {
  runApp(const TelegramCustomApp());
}

class TelegramCustomApp extends StatelessWidget {
  const TelegramCustomApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'تليجرام',
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF17212B),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF242F3D),
          elevation: 0,
        ),
      ),
      locale: const Locale('ar', 'IQ'),
      supportedLocales: const [Locale('ar', 'IQ'), Locale('ar')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const TelegramMainScreen(),
    );
  }
}

class TelegramMainScreen extends StatefulWidget {
  const TelegramMainScreen({super.key});

  @override
  State<TelegramMainScreen> createState() => _TelegramMainScreenState();
}

class _TelegramMainScreenState extends State<TelegramMainScreen> {
  late final WebViewController _controller;
  bool isStealthMode = false;

  @override
  void initState() {
    super.initState();

    late final PlatformWebViewControllerCreationParams params;
    if (WebViewPlatform.instance is AndroidWebViewPlatform) {
      params = AndroidWebViewControllerCreationParams();
    } else {
      params = const PlatformWebViewControllerCreationParams();
    }

    final WebViewController controller =
        WebViewController.fromPlatformCreationParams(params);

    controller
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setUserAgent(
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
      )
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (String url) {
            _unrestrictContent();
          },
        ),
      );

    // تفعيل إعدادات السرعة وتسريع الأداء للـ WebView
    if (controller.platform is AndroidWebViewController) {
      final AndroidWebViewController androidController =
          controller.platform as AndroidWebViewController;
      androidController.setMediaPlaybackRequiresUserGesture(false);
      androidController.setDomStorageEnabled(true);
    }

    // تحميل النسخة العربية مباشرة
    controller.loadRequest(
      Uri.parse('https://web.telegram.org/k/#lang=ar'),
    );

    _controller = controller;
  }

  // فك حظر التنزيل من القنوات المقيدة
  void _unrestrictContent() {
    final jsScript = '''
      document.addEventListener('contextmenu', function(e) {
        e.stopPropagation();
      }, true);

      document.addEventListener('copy', function(e) {
        e.stopPropagation();
      }, true);

      document.addEventListener('selectstart', function(e) {
        e.stopPropagation();
      }, true);

      const style = document.createElement('style');
      style.innerHTML = `
        * {
          user-select: text !important;
          -webkit-user-select: text !important;
          -webkit-touch-callout: default !important;
        }
      `;
      document.head.appendChild(style);

      // التنزيل المباشر عند النقر المزدوج على الوسائط
      document.addEventListener('dblclick', function(e) {
        const target = e.target;
        if (target.tagName === 'VIDEO' || target.tagName === 'IMG') {
          const src = target.src || target.currentSrc;
          if (src) {
            const a = document.createElement('a');
            a.href = src;
            a.download = 'telegram_media_' + Date.now();
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
          }
        }
      });
    ''';
    _controller.runJavaScript(jsScript);
  }

  // وضع التخفي الحقيقي والشامل 100% لمنع إرسال أي إشارة مشاهدة ستوري
  void _toggleStealthMode(bool value) {
    setState(() {
      isStealthMode = value;
    });

    final jsScript = '''
      window._stealthMode = $value;
      if (!window._stealthInjected) {
        window._stealthInjected = true;

        // 1. اعتراض طلبات الـ Fetch
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
          const url = args[0] ? args[0].toString().toLowerCase() : '';
          if (window._stealthMode && (url.includes('story') || url.includes('stories') || url.includes('read') || url.includes('view'))) {
            return new Response(JSON.stringify({ok: true}), {status: 200});
          }
          return originalFetch.apply(this, args);
        };

        // 2. اعتراض طلبات الـ XMLHttpRequest
        const originalXHR = window.XMLHttpRequest.prototype.open;
        window.XMLHttpRequest.prototype.open = function(method, url, ...args) {
          this._url = url ? url.toString().toLowerCase() : '';
          return originalXHR.apply(this, [method, url, ...args]);
        };
        const originalSend = window.XMLHttpRequest.prototype.send;
        window.XMLHttpRequest.prototype.send = function(body) {
          if (window._stealthMode && this._url && (this._url.includes('story') || this._url.includes('stories') || this._url.includes('read') || this._url.includes('view'))) {
            Object.defineProperty(this, 'readyState', {value: 4});
            Object.defineProperty(this, 'status', {value: 200});
            Object.defineProperty(this, 'responseText', {value: '{"ok":true}'});
            if (this.onload) this.onload();
            return;
          }
          return originalSend.apply(this, [body]);
        };

        // 3. اعتراض اتصالات الـ WebSocket وتحليل الحزم النصية والثنائية لمنع إرسال مشاهدات الستوري
        const OriginalWebSocket = window.WebSocket;
        window.WebSocket = function(url, protocol) {
          const ws = new OriginalWebSocket(url, protocol);
          const originalWsSend = ws.send;
          ws.send = function(data) {
            if (window._stealthMode) {
              try {
                if (typeof data === 'string') {
                  const lower = data.toLowerCase();
                  if (lower.includes('story') || lower.includes('stories') || lower.includes('readstories') || lower.includes('incrementstoryviews')) {
                    return; // إلغاء إرسال الحزمة
                  }
                } else if (data instanceof ArrayBuffer || data instanceof Uint8Array || ArrayBuffer.isView(data)) {
                  const bytes = data instanceof ArrayBuffer ? new Uint8Array(data) : new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
                  let decoded = '';
                  for (let i = 0; i < Math.min(bytes.length, 512); i++) {
                    const b = bytes[i];
                    if (b >= 32 && b <= 126) decoded += String.fromCharCode(b);
                  }
                  const lowerDecoded = decoded.toLowerCase();
                  if (lowerDecoded.includes('story') || lowerDecoded.includes('read') || lowerDecoded.includes('stories')) {
                    return; // منع إرسال الحزمة المرتبطة بالستوري
                  }
                }
              } catch(e) {}
            }
            return originalWsSend.call(this, data);
          };
          return ws;
        };
      }
    ''';

    _controller.runJavaScript(jsScript);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          value ? 'تم تفعيل وضع التخفي الحقيقي 🛡️' : 'تم تعطيل وضع التخفي',
          style: const TextStyle(fontFamily: 'sans-serif'),
        ),
        duration: const Duration(seconds: 1),
        backgroundColor: value ? Colors.green : Colors.redAccent,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text(
            'تليجرام',
            style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold),
          ),
          actions: [
            Row(
              children: [
                Icon(
                  isStealthMode ? Icons.visibility_off : Icons.visibility,
                  color: isStealthMode ? Colors.greenAccent : Colors.grey,
                  size: 20,
                ),
                const SizedBox(width: 4),
                Switch(
                  value: isStealthMode,
                  activeColor: Colors.greenAccent,
                  onChanged: _toggleStealthMode,
                ),
              ],
            ),
          ],
        ),
        body: SafeArea(
          child: WebViewWidget(controller: _controller),
        ),
      ),
    );
  }
}
