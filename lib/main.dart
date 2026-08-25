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

    if (controller.platform is AndroidWebViewController) {
      final AndroidWebViewController androidController =
          controller.platform as AndroidWebViewController;
      androidController.setMediaPlaybackRequiresUserGesture(false);
    }

    controller.clearCache();

    controller.loadRequest(
      Uri.parse('https://web.telegram.org/k/#lang=ar'),
    );

    _controller = controller;
  }

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

  void _toggleStealthMode(bool value) {
    setState(() {
      isStealthMode = value;
    });

    final jsScript = '''
      window._stealthMode = $value;
      if (!window._stealthInjected) {
        window._stealthInjected = true;
        const originalFetch = window.fetch;
        window.fetch = async function(...args) {
          const url = args[0] ? args[0].toString() : '';
          if (window._stealthMode && (url.includes('readStories') || url.includes('viewStory') || url.includes('stories'))) {
            return new Response(JSON.stringify({ok: true}), {status: 200});
          }
          return originalFetch.apply(this, args);
        };
      }
    ''';

    _controller.runJavaScript(jsScript);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          value
              ? 'تم تفعيل وضع التخفي'
              : 'تم تعطيل وضع التخفي',
        ),
        duration: const Duration(seconds: 2),
        backgroundColor: value ? Colors.green : Colors.redAccent,
      ),
    );
  }

  void _navigateFolder(bool next) {
    final direction = next ? 'Right' : 'Left';
    final jsCommand = '''
      document.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'Arrow$direction',
        code: 'Arrow$direction',
        altKey: true,
        shiftKey: true,
        bubbles: true
      }));
    ''';
    _controller.runJavaScript(jsCommand);
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
        body: GestureDetector(
          onHorizontalDragEnd: (details) {
            if (details.primaryVelocity != null) {
              if (details.primaryVelocity! < -300) {
                _navigateFolder(true);
              } else if (details.primaryVelocity! > 300) {
                _navigateFolder(false);
              }
            }
          },
          child: SafeArea(
            child: WebViewWidget(controller: _controller),
          ),
        ),
      ),
    );
  }
}
