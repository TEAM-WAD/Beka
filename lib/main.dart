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
      // إجبار التطبيق على اللغة العربية والاتجاه من اليمين لليسار
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
  bool isStealthMode = false; // حالة وضع التخفي

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
      );

    if (controller.platform is AndroidWebViewController) {
      final AndroidWebViewController androidController =
          controller.platform as AndroidWebViewController;
      androidController.setMediaPlaybackRequiresUserGesture(false);
      androidController.setCacheMode(AndroidCacheMode.noCache);
    }

    // تحميل النسخة العربية من تليجرام ويب
    controller.loadRequest(
      Uri.parse('https://web.telegram.org/k/#lang=ar'),
    );

    _controller = controller;
  }

  // تفعيل / تعطيل وضع التخفي لحجب تسجيل مشاهدات الستوري
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
              ? 'تم تفعيل وضع التخفي (لن يتم تسجيل مشاهدتك للستوريات)'
              : 'تم تعطيل وضع التخفي',
          style: const TextStyle(fontFamily: 'sans-serif'),
        ),
        duration: const Duration(seconds: 2),
        backgroundColor: value ? Colors.green : Colors.redAccent,
      ),
    );
  }

  // التمرير السريع بين مجلدات المحادثات عبر محاكاة مفاتيح الكيبورد في التليجرام
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
            // زر وضع التخفي في السويتش
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
          // التعرف على السحب لليمين واليسار للتنقل بين المجلدات بكفاءة
          onHorizontalDragEnd: (details) {
            if (details.primaryVelocity != null) {
              if (details.primaryVelocity! < -300) {
                // سحب نحو اليسار (المجلد التالي)
                _navigateFolder(true);
              } else if (details.primaryVelocity! > 300) {
                // سحب نحو اليمين (المجلد السابق)
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
