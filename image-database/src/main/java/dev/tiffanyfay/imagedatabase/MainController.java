package dev.tiffanyfay.imagedatabase;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.ModelAndView;

import java.util.Collection;
import java.util.Map;

@RestController // This means that this class is a RestController
public class MainController {

    private final ImageRepository imageRepository;

    public MainController(ImageRepository imageRepository) {
        this.imageRepository = imageRepository;
    }

    @PostMapping(value = "/images", consumes = MediaType.APPLICATION_FORM_URLENCODED_VALUE)
    void add (@RequestParam String prompt, @RequestParam String url) {
        imageRepository.save(new ImagePrompt(null, prompt, url));
    }

    @PostMapping(value = "/images", consumes = MediaType.APPLICATION_JSON_VALUE)
    void addJson(@RequestBody ImagePrompt image) {
        imageRepository.save(new ImagePrompt(null, image.prompt(), image.url()));
    }

    @ResponseBody
    @GetMapping("/images")
    Collection<ImagePrompt> all() {
        return this.imageRepository.findAll();
    }

    // model-view-controller
    @GetMapping({"/", "/images.html"})
    ModelAndView allHtml() {
        // src/main/resources/templates/ + STRING + .html
        var map = Map.of("images", this.imageRepository.findAll());
        return new ModelAndView("images", map);
    }
}
